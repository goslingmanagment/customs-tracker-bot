"""Deadline change logic + in-memory pending state."""

import re
import time
from dataclasses import dataclass
from datetime import datetime

import structlog
from aiogram.types import Message, User
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import runtime
from core.constants import POSTPONE_ALLOWED_STATUSES, POSTPONE_TTL_SECONDS
from core.permissions import can_change_deadline
from core.text_utils import user_display_name
from db.models import Task
from db.repo import task_repo
from ui.cards import get_card_for_status

logger = structlog.get_logger()

DATE_INPUT_PATTERN = re.compile(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$")


# --- In-memory pending state ---


@dataclass
class PendingPostpone:
    task_id: int
    chat_id: int
    topic_id: int | None
    expires_at: float
    prompt_message_id: int | None = None


_PENDING_POSTPONES: dict[int, PendingPostpone] = {}


def _cleanup_expired(now: float | None = None) -> None:
    timestamp = now if now is not None else time.time()
    expired_user_ids = [
        user_id
        for user_id, pending in _PENDING_POSTPONES.items()
        if pending.expires_at <= timestamp
    ]
    for user_id in expired_user_ids:
        _PENDING_POSTPONES.pop(user_id, None)


def set_pending_postpone(
    user_id: int,
    task_id: int,
    chat_id: int,
    topic_id: int | None,
    prompt_message_id: int | None = None,
    ttl_seconds: int = POSTPONE_TTL_SECONDS,
) -> None:
    _cleanup_expired()
    _PENDING_POSTPONES[user_id] = PendingPostpone(
        task_id=task_id,
        chat_id=chat_id,
        topic_id=topic_id,
        expires_at=time.time() + max(ttl_seconds, 1),
        prompt_message_id=prompt_message_id,
    )


def get_pending_postpone(user_id: int, now: float | None = None) -> PendingPostpone | None:
    timestamp = now if now is not None else time.time()
    pending = _PENDING_POSTPONES.get(user_id)
    if not pending:
        return None
    if pending.expires_at <= timestamp:
        _PENDING_POSTPONES.pop(user_id, None)
        return None
    return pending


def pop_expired_pending_postpone(
    user_id: int, now: float | None = None
) -> PendingPostpone | None:
    timestamp = now if now is not None else time.time()
    pending = _PENDING_POSTPONES.get(user_id)
    if not pending:
        return None
    if pending.expires_at > timestamp:
        return None
    _PENDING_POSTPONES.pop(user_id, None)
    return pending


def clear_pending_postpone(user_id: int) -> None:
    _PENDING_POSTPONES.pop(user_id, None)


async def clear_pending_postpone_prompt_markup(bot, pending: PendingPostpone | None) -> None:
    if pending is None or pending.prompt_message_id is None:
        return
    try:
        await bot.edit_message_reply_markup(
            chat_id=pending.chat_id,
            message_id=pending.prompt_message_id,
            reply_markup=None,
        )
    except Exception as exc:
        logger.warning(
            "postpone_prompt_markup_clear_failed",
            task_id=pending.task_id,
            chat_id=pending.chat_id,
            message_id=pending.prompt_message_id,
            error=str(exc),
        )


# --- Deadline change logic ---


def postpone_status_error(status: str) -> str | None:
    if status in POSTPONE_ALLOWED_STATUSES:
        return None
    if status == "draft":
        return "Бриф ещё не подтверждён — измените исходное сообщение"
    return "Дедлайн нельзя менять в этом статусе"


def _parse_deadline_input(text: str) -> tuple[str, str] | None:
    match = DATE_INPUT_PATTERN.fullmatch(text.strip())
    if not match:
        return None

    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3)) if match.group(3) else datetime.now().year

    datetime(year, month, day)  # Validation
    return f"{year}-{month:02d}-{day:02d}", f"{day:02d}.{month:02d}"


async def _apply_deadline_change(
    session: AsyncSession,
    message: Message,
    task: Task,
    new_deadline: str,
    display_deadline: str,
) -> None:
    user = message.from_user
    await task_repo.update_task_deadline(
        session,
        task,
        new_deadline,
        changed_by_id=user.id if user else None,
        changed_by_name=(user.username or user.full_name) if user else None,
    )
    await session.commit()

    if task.bot_message_id:
        card_text, keyboard = get_card_for_status(task)
        try:
            await message.bot.edit_message_text(
                card_text,
                chat_id=task.chat_id,
                message_id=task.bot_message_id,
                reply_markup=keyboard,
            )
        except Exception as exc:
            logger.error("card_update_failed", task_id=task.id, error=str(exc))

    await message.bot.send_message(
        chat_id=task.chat_id,
        message_thread_id=task.topic_id,
        text=(
            f"📅 {user_display_name(user)} перенёс(ла) дедлайн кастома #{task.id:03d} "
            f"→ {display_deadline}"
        ),
    )


async def process_deadline_change_text(
    session: AsyncSession,
    message: Message,
    task: Task,
    text: str | None = None,
) -> str:
    payload = text if text is not None else (message.text or message.caption or "")
    if not payload:
        return "no_match"

    if not DATE_INPUT_PATTERN.fullmatch(payload.strip()):
        return "no_match"

    if not can_change_deadline(message.from_user):
        await message.reply("Только администраторы, тимлиды и модели могут менять дедлайн")
        return "forbidden"

    status_error = postpone_status_error(task.status)
    if status_error:
        await message.reply(status_error)
        return "status_blocked"

    try:
        parsed = _parse_deadline_input(payload)
        if parsed is None:
            return "no_match"
        new_deadline, display_deadline = parsed
    except ValueError:
        await message.reply(f"Некорректная дата: {payload.strip()}")
        return "invalid_date"

    await _apply_deadline_change(
        session=session,
        message=message,
        task=task,
        new_deadline=new_deadline,
        display_deadline=display_deadline,
    )
    return "updated"


async def maybe_process_pending_postpone(message: Message) -> bool:
    user = message.from_user
    if not user:
        return False

    expired = pop_expired_pending_postpone(user.id)
    if expired:
        if (
            message.chat.id == expired.chat_id
            and message.message_thread_id == expired.topic_id
        ):
            await clear_pending_postpone_prompt_markup(message.bot, expired)
            await message.reply(
                "Время для ввода даты истекло. Нажмите ⏰ снова."
            )
            return True
        return False

    pending = get_pending_postpone(user.id)
    if not pending:
        return False

    if message.chat.id != pending.chat_id:
        return False

    if message.message_thread_id != pending.topic_id:
        return False

    payload = message.text or message.caption or ""
    if not DATE_INPUT_PATTERN.fullmatch(payload.strip()):
        return False

    from db.engine import async_session

    async with async_session() as session:
        task = await task_repo.get_task_by_id(session, pending.task_id)
        if not task:
            clear_pending_postpone(user.id)
            await clear_pending_postpone_prompt_markup(message.bot, pending)
            await message.reply("Кастом не найден")
            return True

        status = await process_deadline_change_text(session, message, task, payload)
        if status in {"updated", "forbidden", "status_blocked"}:
            clear_pending_postpone(user.id)
            await clear_pending_postpone_prompt_markup(message.bot, pending)
        return status != "no_match"
