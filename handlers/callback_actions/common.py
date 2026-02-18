"""Shared helpers for task callback actions."""

import time
from datetime import datetime
from typing import Any

import structlog
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import roles
from core.permissions import is_admin_or_teamlead, is_model
from db.models import Task
from ui.cards import get_card_for_status

logger = structlog.get_logger()

MODEL_ONLY_ACTIONS = {"take", "finish"}
ADMIN_OR_TEAMLEAD_ACTIONS = {
    "confirm_brief",
    "not_task",
    "not_task_confirm",
    "not_task_cancel",
    "delivered",
    "confirm_delivered",
}
ADMIN_OR_TEAMLEAD_OR_MODEL_ACTIONS = {
    "postpone",
    "postpone_1d",
    "postpone_3d",
    "postpone_7d",
    "cancel_postpone",
    "confirm_shot",
    "deny_shot",
    "deny_delivered",
}

DELETE_CONFIRM_TTL_SECONDS = 10
_PENDING_DELETE_CONFIRMATIONS: dict[tuple[int, int], float] = {}


def parse_callback(data: str) -> tuple[int, str] | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "task":
        return None
    try:
        return int(parts[1]), parts[2]
    except ValueError:
        return None


def is_allowed(action: str, user: Any) -> bool:
    if action in MODEL_ONLY_ACTIONS:
        return is_model(user)
    if action in ADMIN_OR_TEAMLEAD_ACTIONS:
        return is_admin_or_teamlead(user)
    if action in ADMIN_OR_TEAMLEAD_OR_MODEL_ACTIONS:
        return is_admin_or_teamlead(user) or is_model(user)
    return True


def denied_message(action: str) -> str:
    if action in MODEL_ONLY_ACTIONS:
        return "Действие доступно только модели"
    if action in ADMIN_OR_TEAMLEAD_ACTIONS:
        return "Действие доступно только администраторам и тимлидам"
    if action in ADMIN_OR_TEAMLEAD_OR_MODEL_ACTIONS:
        return "Действие доступно только администраторам, тимлидам и модели"
    return "Действие недоступно"


def model_mentions() -> str:
    mentions: list[str] = []
    for username in roles.model_usernames:
        if username:
            mentions.append(f"@{username}")
    for user_id in roles.model_ids:
        mentions.append(f'<a href="tg://user?id={int(user_id)}">model</a>')
    deduped: list[str] = []
    for mention in mentions:
        if mention not in deduped:
            deduped.append(mention)
    return " ".join(deduped)


async def send_feedback(bot, task: Task, text: str, reply_markup=None):
    return await bot.send_message(
        chat_id=task.chat_id,
        text=text,
        message_thread_id=task.topic_id,
        reply_markup=reply_markup,
    )


async def send_feedback_best_effort(
    bot,
    task: Task,
    text: str,
    reply_markup=None,
    *,
    event: str,
) -> bool:
    try:
        await send_feedback(bot, task, text, reply_markup=reply_markup)
        return True
    except Exception as exc:
        logger.error(
            "feedback_send_failed",
            event=event,
            task_id=task.id,
            error=str(exc),
        )
        return False


async def commit_session_safely(
    session: AsyncSession,
    callback: CallbackQuery,
    *,
    action: str,
    task_id: int | None = None,
) -> bool:
    try:
        await session.commit()
        return True
    except Exception as exc:
        try:
            await session.rollback()
        except Exception as rollback_exc:
            logger.error(
                "callback_commit_rollback_failed",
                action=action,
                task_id=task_id,
                error=str(rollback_exc),
            )
        logger.error(
            "callback_commit_failed",
            action=action,
            task_id=task_id,
            error=str(exc),
        )
        try:
            await callback.answer("Не удалось сохранить изменения. Попробуйте ещё раз.")
        except Exception as answer_exc:
            logger.error(
                "callback_commit_error_answer_failed",
                action=action,
                task_id=task_id,
                error=str(answer_exc),
            )
        return False


def format_deadline_for_prompt(deadline: str | None) -> str:
    if not deadline:
        return "не задан"
    try:
        return datetime.strptime(deadline, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return deadline


def card_refresh_note(task_id: int) -> str:
    return (
        f"\n⚠️ Карточку не удалось обновить автоматически. "
        f"Откройте /task {task_id}."
    )


def _cleanup_delete_confirmation(now: float | None = None) -> None:
    timestamp = now if now is not None else time.time()
    expired = [
        key for key, expires_at in _PENDING_DELETE_CONFIRMATIONS.items()
        if expires_at <= timestamp
    ]
    for key in expired:
        _PENDING_DELETE_CONFIRMATIONS.pop(key, None)


def set_delete_confirmation(user_id: int, task_id: int) -> None:
    _cleanup_delete_confirmation()
    _PENDING_DELETE_CONFIRMATIONS[(user_id, task_id)] = (
        time.time() + DELETE_CONFIRM_TTL_SECONDS
    )


def consume_delete_confirmation(user_id: int, task_id: int) -> bool:
    _cleanup_delete_confirmation()
    key = (user_id, task_id)
    if key not in _PENDING_DELETE_CONFIRMATIONS:
        return False
    _PENDING_DELETE_CONFIRMATIONS.pop(key, None)
    return True


def clear_delete_confirmation(user_id: int, task_id: int) -> None:
    _PENDING_DELETE_CONFIRMATIONS.pop((user_id, task_id), None)


async def safe_delete_message(callback: CallbackQuery, task_id: int) -> bool:
    if not callback.message:
        logger.error("callback_message_missing", task_id=task_id)
        return False
    try:
        await callback.message.delete()
        return True
    except Exception as exc:
        logger.error("callback_delete_failed", task_id=task_id, error=str(exc))
        return False


async def refresh_card(callback: CallbackQuery, task: Task) -> bool:
    text, keyboard = get_card_for_status(task)
    target_message_ids: list[int] = []
    if callback.message:
        target_message_ids.append(callback.message.message_id)
    if task.bot_message_id is not None:
        target_message_ids.append(task.bot_message_id)

    # Keep original priority (clicked card first), but avoid duplicate edits.
    deduped_targets: list[int] = []
    seen: set[int] = set()
    for message_id in target_message_ids:
        if message_id in seen:
            continue
        seen.add(message_id)
        deduped_targets.append(message_id)

    if not deduped_targets:
        logger.error("task_card_message_missing", task_id=task.id)
        return False

    expected_primary_target = deduped_targets[0]
    refreshed_primary_target = False
    for target_message_id in deduped_targets:
        try:
            await callback.bot.edit_message_text(
                text,
                chat_id=task.chat_id,
                message_id=target_message_id,
                reply_markup=keyboard,
            )
            if target_message_id == expected_primary_target:
                refreshed_primary_target = True
        except Exception as exc:
            error_text = str(exc)
            # Telegram returns "message is not modified" when content/markup matches.
            if "message is not modified" in error_text.lower():
                if target_message_id == expected_primary_target:
                    refreshed_primary_target = True
                continue
            logger.error(
                "card_update_failed",
                task_id=task.id,
                message_id=target_message_id,
                error=error_text,
            )
    return refreshed_primary_target
