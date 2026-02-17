"""AI retry queue CRUD. Repos never commit — callers commit."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AIRetryQueue


async def enqueue_ai_retry(
    session: AsyncSession,
    *,
    chat_id: int,
    message_id: int,
    topic_id: int | None,
    raw_text: str,
    has_photo: bool,
    sender_username: str | None = None,
    error_detail: str | None = None,
    next_retry_at: str | None = None,
) -> AIRetryQueue:
    now_iso = datetime.now(timezone.utc).isoformat()
    due_at = next_retry_at or now_iso
    result = await session.execute(
        select(AIRetryQueue).where(
            AIRetryQueue.chat_id == chat_id,
            AIRetryQueue.message_id == message_id,
        )
    )
    row = result.scalar_one_or_none()

    if row:
        row.topic_id = topic_id
        row.raw_text = raw_text
        row.has_photo = bool(has_photo)
        row.sender_username = sender_username
        row.last_error = error_detail
        row.next_retry_at = due_at
        row.updated_at = now_iso
        if not row.first_enqueued_at:
            row.first_enqueued_at = now_iso
    else:
        row = AIRetryQueue(
            chat_id=chat_id,
            message_id=message_id,
            topic_id=topic_id,
            raw_text=raw_text,
            has_photo=bool(has_photo),
            sender_username=sender_username,
            attempt_count=0,
            first_enqueued_at=now_iso,
            next_retry_at=due_at,
            last_error=error_detail,
        )
        session.add(row)

    await session.flush()
    return row


async def get_ai_retry_by_id(session: AsyncSession, queue_id: int) -> AIRetryQueue | None:
    result = await session.execute(select(AIRetryQueue).where(AIRetryQueue.id == queue_id))
    return result.scalar_one_or_none()


async def get_due_ai_retries(
    session: AsyncSession,
    *,
    now_iso: str | None = None,
    limit: int = 20,
) -> list[AIRetryQueue]:
    due = now_iso or datetime.now(timezone.utc).isoformat()
    result = await session.execute(
        select(AIRetryQueue)
        .where(AIRetryQueue.next_retry_at <= due)
        .order_by(AIRetryQueue.next_retry_at.asc(), AIRetryQueue.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def reschedule_ai_retry(
    session: AsyncSession,
    row: AIRetryQueue,
    *,
    attempt_count: int,
    next_retry_at: str,
    last_error: str | None = None,
) -> AIRetryQueue:
    row.attempt_count = int(attempt_count)
    row.next_retry_at = next_retry_at
    row.last_error = last_error
    row.updated_at = datetime.now(timezone.utc).isoformat()
    await session.flush()
    return row


async def delete_ai_retry(session: AsyncSession, row: AIRetryQueue) -> None:
    await session.delete(row)
    await session.flush()
