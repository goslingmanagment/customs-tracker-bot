"""AI retry queue processing."""

from datetime import datetime, timedelta, timezone

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from ai.classifier import classify_message
from core.config import runtime
from core.constants import MAX_RETRY_ATTEMPTS, MAX_RETRY_WINDOW, RETRY_BACKOFF_MINUTES
from core.exceptions import AITransientError
from db.repo import message_repo, retry_repo, task_repo
from services.task_service import build_task_kwargs, sanitize_ai_data
from ui.cards import build_draft_card

logger = structlog.get_logger()


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def _send_retry_exhausted_alert(bot: Bot, row) -> None:
    alert_chat_id = row.chat_id or runtime.customs_chat_id
    alert_topic_id = row.topic_id if row.topic_id is not None else runtime.customs_topic_id
    if not alert_chat_id:
        return
    try:
        await bot.send_message(
            chat_id=alert_chat_id,
            message_thread_id=alert_topic_id,
            reply_to_message_id=row.message_id,
            text=(
                f"⚠️ Не удалось автоматически распознать бриф из сообщения #{row.message_id} "
                f"после {MAX_RETRY_ATTEMPTS} попыток. Проверьте вручную через /add."
            ),
        )
    except Exception as exc:
        logger.error(
            "ai_retry_exhausted_alert_send_error",
            queue_id=row.id, chat_id=alert_chat_id,
            topic_id=alert_topic_id, error=str(exc),
        )


async def _reschedule_or_fail(
    session: AsyncSession, bot: Bot,
    *, queue_id: int, now: datetime, error_message: str,
) -> None:
    row = await retry_repo.get_ai_retry_by_id(session, queue_id)
    if not row:
        return

    attempts = int(row.attempt_count or 0) + 1
    first_enqueued_at = _parse_iso_timestamp(row.first_enqueued_at) or now
    retry_window_elapsed = (now - first_enqueued_at) >= MAX_RETRY_WINDOW
    exhausted = attempts >= MAX_RETRY_ATTEMPTS or retry_window_elapsed

    if exhausted:
        await message_repo.log_parse_failure(
            session, message_id=row.message_id, raw_text=row.raw_text,
            error_type="transient_retries_exhausted", error_detail=error_message,
        )
        await message_repo.mark_message_processed(
            session, chat_id=row.chat_id, message_id=row.message_id, is_task=False,
        )
        await retry_repo.delete_ai_retry(session, row)
        await session.commit()
        await _send_retry_exhausted_alert(bot, row)
        logger.error(
            "ai_retry_exhausted", queue_id=row.id,
            message_id=row.message_id, attempts=attempts, error=error_message,
        )
        return

    backoff_minutes = RETRY_BACKOFF_MINUTES[min(attempts - 1, len(RETRY_BACKOFF_MINUTES) - 1)]
    next_retry_at = (now + timedelta(minutes=backoff_minutes)).isoformat()
    await retry_repo.reschedule_ai_retry(
        session, row,
        attempt_count=attempts, next_retry_at=next_retry_at, last_error=error_message,
    )
    await session.commit()
    logger.warning(
        "ai_retry_rescheduled", queue_id=row.id, message_id=row.message_id,
        attempts=attempts, next_retry_at=next_retry_at, error=error_message,
    )


async def _process_single_retry(bot: Bot, queue_id: int, session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    row = await retry_repo.get_ai_retry_by_id(session, queue_id)
    if not row:
        return

    if await message_repo.is_message_processed(session, row.chat_id, row.message_id):
        await retry_repo.delete_ai_retry(session, row)
        await session.commit()
        logger.info("ai_retry_removed_already_processed", queue_id=row.id, message_id=row.message_id)
        return

    existing_task = await task_repo.get_task_by_message(session, row.chat_id, row.message_id)
    if existing_task:
        await message_repo.mark_message_processed(
            session, chat_id=row.chat_id, message_id=row.message_id, is_task=True,
        )
        await retry_repo.delete_ai_retry(session, row)
        await session.commit()
        logger.info("ai_retry_removed_existing_task", queue_id=row.id, task_id=existing_task.id)
        return

    try:
        result = await classify_message(row.raw_text, bool(row.has_photo))
    except AITransientError:
        await _reschedule_or_fail(
            session, bot, queue_id=queue_id, now=now, error_message="TRANSIENT_ERROR",
        )
        return

    if result is None:
        await message_repo.log_parse_failure(
            session, message_id=row.message_id, raw_text=row.raw_text,
            error_type="api_error", error_detail="AI returned None during retry processing",
        )
        await message_repo.mark_message_processed(
            session, chat_id=row.chat_id, message_id=row.message_id, is_task=False,
        )
        await retry_repo.delete_ai_retry(session, row)
        await session.commit()
        logger.warning("ai_retry_permanent_failure", queue_id=row.id, message_id=row.message_id)
        return

    is_task = bool(result.get("is_task", False))
    confidence = float(result.get("confidence", 0) or 0)
    if not is_task or confidence < runtime.ai_confidence_threshold:
        await message_repo.mark_message_processed(
            session, chat_id=row.chat_id, message_id=row.message_id, is_task=False,
        )
        await retry_repo.delete_ai_retry(session, row)
        await session.commit()
        logger.info(
            "ai_retry_non_task_or_low_confidence", queue_id=row.id,
            is_task=is_task, confidence=confidence,
            threshold=runtime.ai_confidence_threshold,
        )
        return

    data = sanitize_ai_data(result.get("data", {}) or {})
    kwargs = build_task_kwargs(
        data,
        message_id=row.message_id, chat_id=row.chat_id,
        topic_id=row.topic_id, raw_text=row.raw_text,
        ai_confidence=confidence, sender_username=row.sender_username,
    )

    try:
        task, created = await task_repo.create_task(session, **kwargs)
    except Exception as exc:
        await session.rollback()
        await _reschedule_or_fail(
            session, bot, queue_id=queue_id, now=now,
            error_message=f"task_create_failed: {exc}",
        )
        return

    if not created:
        await message_repo.mark_message_processed(
            session, chat_id=row.chat_id, message_id=row.message_id, is_task=True,
        )
        await retry_repo.delete_ai_retry(session, row)
        await session.commit()
        logger.info("ai_retry_task_already_exists", queue_id=row.id, task_id=task.id)
        return

    card_text, keyboard = build_draft_card(task)
    try:
        sent = await bot.send_message(
            chat_id=row.chat_id,
            message_thread_id=row.topic_id,
            reply_to_message_id=row.message_id,
            text=card_text,
            reply_markup=keyboard,
        )
    except Exception as exc:
        await session.rollback()
        await _reschedule_or_fail(
            session, bot, queue_id=queue_id, now=now,
            error_message=f"task_card_send_failed: {exc}",
        )
        return

    await task_repo.update_task_bot_message_id(session, task, sent.message_id)
    await message_repo.mark_message_processed(
        session, chat_id=row.chat_id, message_id=row.message_id, is_task=True,
    )
    await retry_repo.delete_ai_retry(session, row)
    await session.commit()
    logger.info(
        "ai_retry_task_created", queue_id=row.id,
        task_id=task.id, bot_message_id=sent.message_id,
    )


async def process_ai_retry_queue(bot: Bot, session: AsyncSession) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    due_rows = await retry_repo.get_due_ai_retries(session, now_iso=now_iso, limit=20)
    queue_ids = [row.id for row in due_rows]

    for queue_id in queue_ids:
        try:
            await _process_single_retry(bot, queue_id, session)
        except Exception as exc:
            logger.error("ai_retry_processing_error", queue_id=queue_id, error=str(exc))
