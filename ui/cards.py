from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.text_utils import esc
from db.models import Task
from ui.formatters import PRIORITY_EMOJI, STATUS_LABEL, format_amount, format_deadline_status

PLATFORM_LABEL = {
    "fansly": "Fansly",
    "onlyfans": "OnlyFans",
}


def _task_callback(task_id: int, action: str) -> str:
    return f"task:{task_id}:{action}"


def _build_common_header(task: Task, status_icon: str, status_label: str) -> str:
    amount_str = format_amount(task.amount_total, task.payment_note)
    deadline_str = format_deadline_status(task.deadline)

    parts = [f"{status_icon} <b>Кастом #{task.id:03d}</b>", amount_str]
    if deadline_str:
        parts.append(deadline_str)
    parts.append(status_label)
    return " | ".join(parts)


def _build_common_lines(task: Task, status_icon: str, status_label: str) -> list[str]:
    lines = [_build_common_header(task, status_icon, status_label)]
    if task.description:
        lines.append(esc(task.description[:100]))
    if task.duration:
        lines.append(f"⏱ {esc(task.duration)}")

    fan_platform_parts: list[str] = []
    if task.fan_name:
        fan_platform_parts.append(f"👤 {esc(task.fan_name)}")
    if task.platform:
        platform_label = PLATFORM_LABEL.get(task.platform.lower(), task.platform)
        fan_platform_parts.append(f"🌐 {esc(platform_label)}")
    if fan_platform_parts:
        lines.append(" | ".join(fan_platform_parts))

    priority_icon = PRIORITY_EMOJI.get(task.priority, "🟡")
    lines.append(f"{priority_icon} {esc(task.priority)}")
    return lines


def build_draft_card(task: Task) -> tuple[str, InlineKeyboardMarkup]:
    lines = _build_common_lines(task, "📋", STATUS_LABEL["draft"])
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=_task_callback(task.id, "confirm_brief"),
                ),
                InlineKeyboardButton(
                    text="❌ Не бриф",
                    callback_data=_task_callback(task.id, "not_task"),
                ),
            ]
        ]
    )
    return "\n".join(lines), keyboard


def build_awaiting_card(task: Task) -> tuple[str, InlineKeyboardMarkup]:
    lines = _build_common_lines(task, "📦", STATUS_LABEL["awaiting_confirmation"])
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Взяла в работу",
                    callback_data=_task_callback(task.id, "take"),
                ),
                InlineKeyboardButton(
                    text="⏰ Перенести",
                    callback_data=_task_callback(task.id, "postpone"),
                ),
            ]
        ]
    )
    return "\n".join(lines), keyboard


def build_processing_card(task: Task) -> tuple[str, InlineKeyboardMarkup]:
    lines = _build_common_lines(task, "🎬", STATUS_LABEL["processing"])
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📹 Отснято",
                    callback_data=_task_callback(task.id, "finish"),
                ),
                InlineKeyboardButton(
                    text="⏰ Перенести",
                    callback_data=_task_callback(task.id, "postpone"),
                ),
            ]
        ]
    )
    return "\n".join(lines), keyboard


def build_finished_card(task: Task) -> tuple[str, InlineKeyboardMarkup]:
    lines = _build_common_lines(task, "📹", STATUS_LABEL["finished"])
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Доставлено",
                    callback_data=_task_callback(task.id, "delivered"),
                ),
            ]
        ]
    )
    return "\n".join(lines), keyboard


def build_delivered_card(task: Task) -> tuple[str, None]:
    lines = _build_common_lines(task, "✔️", STATUS_LABEL["delivered"])
    return "\n".join(lines), None


def build_cancelled_card(task: Task) -> tuple[str, None]:
    lines = _build_common_lines(task, "🗑", STATUS_LABEL["cancelled"])
    return "\n".join(lines), None


def get_card_for_status(task: Task) -> tuple[str, InlineKeyboardMarkup | None]:
    builders = {
        "draft": build_draft_card,
        "awaiting_confirmation": build_awaiting_card,
        "processing": build_processing_card,
        "finished": build_finished_card,
        "delivered": build_delivered_card,
        "cancelled": build_cancelled_card,
    }
    builder = builders.get(task.status, build_draft_card)
    return builder(task)
