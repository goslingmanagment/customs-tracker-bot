import structlog
from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.permissions import is_admin
from core.text_utils import esc
from db.engine import async_session
from db.repo import role_repo, settings_repo
from diagnostics.readiness import evaluate_brief_env_readiness
from handlers.commands.info import BLOCKER_MESSAGES, WARNING_MESSAGES
from services.role_service import load_role_cache
from services.settings_service import load_runtime_settings

logger = structlog.get_logger()

router = Router()


def _setup_health_text() -> str:
    readiness = evaluate_brief_env_readiness()
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
    return "\n".join(lines)


@router.message(Command("setup"), F.chat.type == ChatType.PRIVATE)
async def cmd_setup_dm(message: Message):
    await message.reply(
        "Добавьте бота в группу с форум-топиками, "
        "откройте нужный топик и отправьте /setup."
    )


@router.message(Command("setup"))
async def cmd_setup(message: Message):
    """Configure working topic and bootstrap the very first admin."""
    chat_id = message.chat.id
    topic_id = message.message_thread_id
    user = message.from_user

    if not topic_id:
        await message.reply(
            "Запустите /setup внутри топика (форум-треда), "
            "а не в основном чате группы."
        )
        return

    first_admin_bootstrapped = False
    async with async_session() as session:
        admins_exist = bool(await role_repo.list_role_members(session, "admin"))
        if admins_exist:
            if not is_admin(user):
                await message.reply(
                    "Только администраторы могут выполнять /setup после первичной настройки"
                )
                return
            if user:
                await role_repo.upsert_role_member(
                    session, "admin",
                    user_id=user.id, username=user.username,
                    created_by_id=user.id,
                    created_by_name=user.username or user.full_name,
                )
        elif user:
            await role_repo.upsert_role_member(
                session, "admin",
                user_id=user.id, username=user.username,
                created_by_id=user.id,
                created_by_name=user.username or user.full_name,
            )
            first_admin_bootstrapped = True

        await settings_repo.upsert_app_settings(
            session, customs_chat_id=chat_id, customs_topic_id=topic_id,
        )
        await session.commit()
        await load_runtime_settings(session)
        await load_role_cache(session)

    username = f"@{user.username}" if user and user.username else ""
    user_id = user.id if user else "?"

    logger.info(
        "setup_completed",
        chat_id=chat_id, topic_id=topic_id,
        admin_id=user_id, first_admin_bootstrapped=first_admin_bootstrapped,
    )

    suffix = (
        "\n\nПервый администратор добавлен автоматически."
        if first_admin_bootstrapped else ""
    )
    admin_display = esc(username) if username else "без username"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Модель", callback_data="setup:add_model"),
                InlineKeyboardButton(text="➕ Тимлид", callback_data="setup:add_teamlead"),
            ],
            [
                InlineKeyboardButton(text="🩺 Проверить", callback_data="setup:health"),
            ],
        ]
    )

    await message.reply(
        "✅ <b>Бот привязан к этому топику</b>\n\n"
        f"<b>Админ:</b> {admin_display} (<code>{user_id}</code>)"
        f"{suffix}\n\n"
        "<b>Следующие шаги:</b>\n"
        "1) Добавьте модель\n"
        "2) Добавьте тимлида (если нужен)\n"
        "3) Проверьте готовность конфигурации",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "setup:add_model")
async def cb_setup_add_model(callback: CallbackQuery):
    if callback.message:
        await callback.message.answer(
            "➕ <b>Как добавить модель</b>\n\n"
            "• Командой: <code>/model add @username</code>\n"
            "• По ID: <code>/model add 123456789</code>\n"
            "• Ответом на сообщение пользователя: <code>/model add</code>"
        )
    await callback.answer()


@router.callback_query(F.data == "setup:add_teamlead")
async def cb_setup_add_teamlead(callback: CallbackQuery):
    if callback.message:
        await callback.message.answer(
            "➕ <b>Как добавить тимлида</b>\n\n"
            "• Командой: <code>/teamlead add @username</code>\n"
            "• По ID: <code>/teamlead add 123456789</code>\n"
            "• Ответом на сообщение пользователя: <code>/teamlead add</code>"
        )
    await callback.answer()


@router.callback_query(F.data == "setup:health")
async def cb_setup_health(callback: CallbackQuery):
    if callback.message:
        await callback.message.answer(_setup_health_text())
    await callback.answer()
