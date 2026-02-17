import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.permissions import is_admin, is_model, is_teamlead
from core.text_utils import esc
from db.engine import async_session
from diagnostics.readiness import (
    BLOCKER_AI_MODEL_MISSING,
    BLOCKER_ANTHROPIC_API_KEY_MISSING,
    BLOCKER_BOT_TOKEN_INVALID_FORMAT,
    BLOCKER_BOT_TOKEN_MISSING,
    BLOCKER_CUSTOMS_CHAT_ID_MISSING,
    BLOCKER_CUSTOMS_TOPIC_ID_MISSING,
    BLOCKER_RUNTIME_SETTINGS_MISSING,
    BLOCKER_TIMEZONE_INVALID,
    WARNING_AI_CONFIDENCE_THRESHOLD_RANGE,
    WARNING_FINISHED_REMINDER_HOURS_INVALID,
    WARNING_HIGH_URGENCY_COOLDOWN_HOURS_INVALID,
    WARNING_OVERDUE_REMINDER_COOLDOWN_HOURS_INVALID,
    WARNING_REMINDER_HOURS_BEFORE_INVALID,
    evaluate_brief_env_readiness,
    summarize_readiness_for_log,
)
from services.role_service import resolve_admin_identity

router = Router()
logger = structlog.get_logger()

BLOCKER_MESSAGES = {
    BLOCKER_BOT_TOKEN_MISSING: "Не задан BOT_TOKEN.",
    BLOCKER_BOT_TOKEN_INVALID_FORMAT: "BOT_TOKEN имеет неверный формат.",
    BLOCKER_CUSTOMS_CHAT_ID_MISSING: "Не задан chat_id в app_settings (выполните /setup).",
    BLOCKER_CUSTOMS_TOPIC_ID_MISSING: "Не задан topic_id в app_settings (выполните /setup).",
    BLOCKER_ANTHROPIC_API_KEY_MISSING: "Не задан ANTHROPIC_API_KEY.",
    BLOCKER_AI_MODEL_MISSING: "Пустой AI_MODEL.",
    BLOCKER_RUNTIME_SETTINGS_MISSING: "Не загружены runtime-настройки из БД.",
    BLOCKER_TIMEZONE_INVALID: "TIMEZONE в runtime-настройках некорректен.",
}

WARNING_MESSAGES = {
    WARNING_AI_CONFIDENCE_THRESHOLD_RANGE: "AI_CONFIDENCE_THRESHOLD вне диапазона 0..1.",
    WARNING_REMINDER_HOURS_BEFORE_INVALID: "REMINDER_HOURS_BEFORE должен быть > 0.",
    WARNING_OVERDUE_REMINDER_COOLDOWN_HOURS_INVALID: (
        "OVERDUE_REMINDER_COOLDOWN_HOURS должен быть > 0."
    ),
    WARNING_HIGH_URGENCY_COOLDOWN_HOURS_INVALID: (
        "HIGH_URGENCY_COOLDOWN_HOURS должен быть > 0."
    ),
    WARNING_FINISHED_REMINDER_HOURS_INVALID: "FINISHED_REMINDER_HOURS должен быть > 0.",
}


@router.message(Command("id"))
async def cmd_id(message: Message):
    lines = [
        f"<b>Chat ID:</b> <code>{message.chat.id}</code>",
    ]
    if message.message_thread_id:
        lines.append(f"<b>Topic ID:</b> <code>{message.message_thread_id}</code>")
    else:
        lines.append("<i>Не в топике (нет thread ID)</i>")
    await message.reply("\n".join(lines))


@router.message(Command("help"))
async def cmd_help(message: Message):
    user = message.from_user
    user_is_admin = is_admin(user)
    user_is_teamlead = is_teamlead(user)
    user_is_model = is_model(user)

    lines = [
        "📖 <b>Команды бота</b>",
        "",
        "<b>Основные:</b>",
        "/status — сводка по активным кастомам (с кнопками быстрого открытия)",
        "/list — список задач (all, active, overdue, draft, awaiting, processing, finished, delivered)",
        "/task {номер} — детали задачи",
        "/help — эта справка",
        "/id — показать chat_id и topic_id",
    ]

    if user_is_admin or user_is_teamlead or user_is_model:
        lines.append("/add — зарегистрировать бриф вручную (ответом на сообщение)")

    if user_is_admin:
        lines.extend([
            "",
            "<b>Админ-команды:</b>",
            "/stats — статистика за месяц",
            "/settings — показать/изменить runtime-настройки",
            "/revert {номер} — вернуть задачу на шаг назад",
            "/setup — привязать бота к топику",
            "/admin — управление администраторами",
            "/model — управление моделями",
            "/teamlead — управление тимлидами",
            "/roles — сводка по всем ролям",
            "/health — проверка конфигурации брифов",
        ])

    lines.extend([
        "",
        "<b>Ответы на карточки:</b>",
        "• Ответьте датой (ДД.ММ или ДД.ММ.ГГГГ), чтобы сменить дедлайн",
        "• Ответьте «снято/отснято» в статусе «В работе», чтобы предложить отметку съёмки",
        "• Ответьте «доставлено/отправлено» в статусе «Отснято», чтобы предложить отметку доставки",
    ])

    await message.reply("\n".join(lines))


@router.message(Command("health"))
async def cmd_health(message: Message):
    from core.config import roles

    admins_configured = bool(roles.admin_ids or roles.admin_usernames)
    if admins_configured and not is_admin(message.from_user):
        await message.reply("Доступно только администраторам")
        return

    if admins_configured and message.from_user:
        async with async_session() as session:
            await resolve_admin_identity(message.from_user, session)

    readiness = evaluate_brief_env_readiness()
    logger.info(
        "health_check_requested",
        request_message_id=message.message_id,
        request_chat_id=message.chat.id,
        request_topic_id=message.message_thread_id,
        request_from_user_id=message.from_user.id if message.from_user else None,
        request_from_username=message.from_user.username if message.from_user else None,
        **summarize_readiness_for_log(readiness),
    )

    lines = ["🩺 <b>Проверка конфигурации брифов</b>"]
    lines.append(f"Статус: {'✅ Готово' if readiness.ready else '❌ Не готово'}")
    lines.append("")

    if readiness.blockers:
        lines.append("Блокеры:")
        for code in readiness.blockers:
            lines.append(f"• {esc(BLOCKER_MESSAGES.get(code, code))}")
        lines.append("")

    if readiness.warnings:
        lines.append("Предупреждения:")
        for code in readiness.warnings:
            lines.append(f"• {esc(WARNING_MESSAGES.get(code, code))}")
        lines.append("")

    lines.append("Что делать:")
    lines.append("1) Проверьте секреты в .env (BOT_TOKEN, ANTHROPIC_API_KEY).")
    lines.append("2) Если бот не привязан — выполните /setup в нужном топике.")
    lines.append("3) Проверьте runtime-настройки в таблице app_settings.")

    await message.reply("\n".join(lines))
