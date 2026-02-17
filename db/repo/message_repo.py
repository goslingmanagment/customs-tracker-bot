"""ProcessedMessage + ParseFailure. Repos never commit — callers commit."""

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ParseFailure, ProcessedMessage

logger = structlog.get_logger()


async def is_message_processed(
    session: AsyncSession, chat_id: int, message_id: int
) -> bool:
    result = await session.execute(
        select(ProcessedMessage).where(
            ProcessedMessage.chat_id == chat_id,
            ProcessedMessage.message_id == message_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def mark_message_processed(
    session: AsyncSession, chat_id: int, message_id: int, is_task: bool = False
) -> None:
    stmt = sqlite_insert(ProcessedMessage).values(
        chat_id=chat_id,
        message_id=message_id,
        is_task=is_task,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProcessedMessage.message_id, ProcessedMessage.chat_id],
        set_={"is_task": is_task},
    )
    await session.execute(stmt)
    await session.flush()


async def log_parse_failure(
    session: AsyncSession,
    message_id: int,
    raw_text: str,
    error_type: str,
    error_detail: str | None = None,
) -> None:
    pf = ParseFailure(
        message_id=message_id,
        raw_text=raw_text,
        error_type=error_type,
        error_detail=error_detail,
    )
    session.add(pf)
    await session.flush()
    logger.warning("parse_failure", message_id=message_id, error_type=error_type)
