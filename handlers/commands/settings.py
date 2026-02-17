"""Admin command for runtime settings stored in app_settings."""

import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.config import runtime
from core.permissions import is_admin
from db.engine import async_session
from db.repo import settings_repo
from handlers.filters import WorkingTopicFilter
from services.role_service import resolve_admin_identity
from services.settings_service import RUNTIME_TIMEZONE, load_runtime_settings

logger = structlog.get_logger()

router = Router()

_SETTINGS_HINTS: dict[str, tuple[str, str]] = {
    "confidence": (
        "Порог уверенности AI. Если ниже порога — бриф не будет авто-принят.",
        "/settings confidence 0.8",
    ),
    "reminder_hours": (
        "За сколько часов до дедлайна отправлять напоминание.",
        "/settings reminder_hours 12",
    ),
    "overdue_cooldown_hours": (
        "Интервал повторных напоминаний для просроченных задач.",
        "/settings overdue_cooldown_hours 4",
    ),
    "high_urgency_cooldown_hours": (
        "Интервал повторных напоминаний для срочных задач.",
        "/settings high_urgency_cooldown_hours 2",
    ),
    "finished_reminder_hours": (
        "Через сколько часов напоминать о задаче в статусе «Отснято».",
        "/settings finished_reminder_hours 24",
    ),
}


def _settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 confidence", callback_data="settings:help:confidence"),
                InlineKeyboardButton(text="⏰ reminder", callback_data="settings:help:reminder_hours"),
            ],
            [
                InlineKeyboardButton(
                    text="🚨 overdue",
                    callback_data="settings:help:overdue_cooldown_hours",
                ),
                InlineKeyboardButton(
                    text="🔥 high urgency",
                    callback_data="settings:help:high_urgency_cooldown_hours",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📹 finished",
                    callback_data="settings:help:finished_reminder_hours",
                ),
                InlineKeyboardButton(text="♻️ reset", callback_data="settings:reset"),
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="settings:show"),
            ],
        ]
    )


def _settings_usage() -> str:
    return (
        "Использование:\n"
        "/settings — показать текущие настройки\n"
        "/settings reset — сбросить runtime-настройки по умолчанию\n"
        "/settings confidence 0.8\n"
        "/settings reminder_hours 12\n"
        "/settings overdue_cooldown_hours 4\n"
        "/settings high_urgency_cooldown_hours 2\n"
        "/settings finished_reminder_hours 24\n"
        "/settings timezone Europe/Kyiv (отключено: timezone фиксирован)"
    )


def _settings_snapshot_text() -> str:
    return (
        "⚙️ <b>Текущие runtime-настройки</b>\n\n"
        f"confidence: <code>{runtime.ai_confidence_threshold:.2f}</code> — "
        "порог уверенности AI (0.0–1.0)\n"
        f"reminder_hours: <code>{runtime.reminder_hours_before}</code> — "
        "напоминание за N часов до дедлайна\n"
        f"overdue_cooldown_hours: <code>{runtime.overdue_reminder_cooldown_hours}</code> — "
        "интервал повторных напоминаний о просрочке\n"
        f"high_urgency_cooldown_hours: <code>{runtime.high_urgency_cooldown_hours}</code> — "
        "интервал для срочных задач\n"
        f"finished_reminder_hours: <code>{runtime.finished_reminder_hours}</code> — "
        "напомнить о недоставленном через N часов\n"
        f"timezone: <code>{runtime.timezone}</code> (фиксировано)\n"
    )


async def _reset_runtime_settings() -> dict:
    async with async_session() as session:
        await settings_repo.upsert_app_settings(
            session,
            ai_confidence_threshold=0.7,
            reminder_hours_before=24,
            overdue_reminder_cooldown_hours=4,
            high_urgency_cooldown_hours=2,
            finished_reminder_hours=24,
        )
        await session.commit()
        return await load_runtime_settings(session)


def _settings_hint_text(key: str) -> str:
    hint = _SETTINGS_HINTS.get(key)
    if hint is None:
        return "Неизвестный параметр."
    description, example = hint
    return (
        f"⚙️ <b>{key}</b>\n\n"
        f"{description}\n"
        f"Текущее значение: <code>{_current_setting_value(key)}</code>\n\n"
        f"Пример: <code>{example}</code>"
    )


def _current_setting_value(key: str) -> str:
    if key == "confidence":
        return f"{runtime.ai_confidence_threshold:.2f}"
    if key == "reminder_hours":
        return str(runtime.reminder_hours_before)
    if key == "overdue_cooldown_hours":
        return str(runtime.overdue_reminder_cooldown_hours)
    if key == "high_urgency_cooldown_hours":
        return str(runtime.high_urgency_cooldown_hours)
    if key == "finished_reminder_hours":
        return str(runtime.finished_reminder_hours)
    return "—"


def _is_working_topic(chat_id: int | None, topic_id: int | None) -> bool:
    return (
        chat_id == runtime.customs_chat_id
        and topic_id == runtime.customs_topic_id
    )


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


@router.message(Command("settings"), WorkingTopicFilter())
async def cmd_settings(message: Message):
    if not is_admin(message.from_user):
        await message.reply("Доступно только администраторам")
        return

    async with async_session() as session:
        await resolve_admin_identity(message.from_user, session)

    args = (message.text or "").split(maxsplit=2)
    if len(args) == 1:
        await message.reply(_settings_snapshot_text(), reply_markup=_settings_keyboard())
        return

    key = args[1].strip().lower()
    if key == "reset":
        runtime_cfg = await _reset_runtime_settings()
        logger.info("settings_reset_to_defaults", **runtime_cfg)
        await message.reply(
            "✅ Runtime-настройки сброшены к значениям по умолчанию\n\n"
            f"{_settings_snapshot_text()}",
            reply_markup=_settings_keyboard(),
        )
        return

    if len(args) < 3:
        await message.reply(_settings_usage())
        return

    raw_value = args[2].strip()

    if key == "timezone":
        await message.reply(
            f"⛔ timezone зафиксирован на <code>{RUNTIME_TIMEZONE}</code>. "
            "Изменение отключено."
        )
        return

    update_kwargs: dict[str, int | float] = {}
    field_label = key

    if key == "confidence":
        value = _parse_float(raw_value)
        if value is None or value < 0 or value > 1:
            await message.reply("confidence должен быть числом в диапазоне 0..1")
            return
        update_kwargs["ai_confidence_threshold"] = value
    elif key == "reminder_hours":
        value = _parse_int(raw_value)
        if value is None or value <= 0:
            await message.reply("reminder_hours должен быть целым числом > 0")
            return
        update_kwargs["reminder_hours_before"] = value
    elif key == "overdue_cooldown_hours":
        value = _parse_int(raw_value)
        if value is None or value <= 0:
            await message.reply("overdue_cooldown_hours должен быть целым числом > 0")
            return
        update_kwargs["overdue_reminder_cooldown_hours"] = value
    elif key == "high_urgency_cooldown_hours":
        value = _parse_int(raw_value)
        if value is None or value <= 0:
            await message.reply("high_urgency_cooldown_hours должен быть целым числом > 0")
            return
        update_kwargs["high_urgency_cooldown_hours"] = value
    elif key == "finished_reminder_hours":
        value = _parse_int(raw_value)
        if value is None or value <= 0:
            await message.reply("finished_reminder_hours должен быть целым числом > 0")
            return
        update_kwargs["finished_reminder_hours"] = value
    else:
        await message.reply(_settings_usage())
        return

    async with async_session() as session:
        await settings_repo.upsert_app_settings(session, **update_kwargs)
        await session.commit()
        runtime_cfg = await load_runtime_settings(session)

    logger.info("settings_updated", field=field_label, value=raw_value, **runtime_cfg)
    await message.reply(
        f"✅ Настройка <code>{field_label}</code> обновлена на <code>{raw_value}</code>\n\n"
        f"{_settings_snapshot_text()}",
        reply_markup=_settings_keyboard(),
    )


def _ensure_settings_callback_access(callback: CallbackQuery) -> bool:
    if not is_admin(callback.from_user):
        return False
    if not callback.message:
        return False
    return _is_working_topic(
        callback.message.chat.id,
        callback.message.message_thread_id,
    )


@router.callback_query(F.data == "settings:show")
async def cb_settings_show(callback: CallbackQuery):
    if not _ensure_settings_callback_access(callback):
        await callback.answer("Доступно только администраторам в рабочем топике")
        return
    if callback.message:
        await callback.message.answer(
            _settings_snapshot_text(),
            reply_markup=_settings_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("settings:help:"))
async def cb_settings_help(callback: CallbackQuery):
    if not _ensure_settings_callback_access(callback):
        await callback.answer("Доступно только администраторам в рабочем топике")
        return
    key = (callback.data or "").split(":", maxsplit=2)[-1]
    if callback.message:
        await callback.message.answer(_settings_hint_text(key))
    await callback.answer()


@router.callback_query(F.data == "settings:reset")
async def cb_settings_reset(callback: CallbackQuery):
    if not _ensure_settings_callback_access(callback):
        await callback.answer("Доступно только администраторам в рабочем топике")
        return

    runtime_cfg = await _reset_runtime_settings()
    logger.info("settings_reset_to_defaults", source="callback", **runtime_cfg)
    if callback.message:
        await callback.message.answer(
            "✅ Runtime-настройки сброшены к значениям по умолчанию\n\n"
            f"{_settings_snapshot_text()}",
            reply_markup=_settings_keyboard(),
        )
    await callback.answer("Сброшено")
