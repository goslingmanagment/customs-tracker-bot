import pytest
from sqlalchemy import select

from db.models import ParseFailure, ProcessedMessage
from db.repo import message_repo


@pytest.mark.asyncio
async def test_mark_message_processed_is_idempotent(db_session):
    await message_repo.mark_message_processed(db_session, chat_id=-1, message_id=100, is_task=False)
    assert await message_repo.is_message_processed(db_session, chat_id=-1, message_id=100)

    await message_repo.mark_message_processed(db_session, chat_id=-1, message_id=100, is_task=True)

    row = (
        await db_session.execute(
            select(ProcessedMessage).where(
                ProcessedMessage.chat_id == -1,
                ProcessedMessage.message_id == 100,
            )
        )
    ).scalar_one()
    assert row.is_task is True


@pytest.mark.asyncio
async def test_log_parse_failure_inserts_row(db_session):
    await message_repo.log_parse_failure(
        db_session,
        message_id=200,
        raw_text="raw",
        error_type="api_error",
        error_detail="boom",
    )

    row = (
        await db_session.execute(select(ParseFailure).where(ParseFailure.message_id == 200))
    ).scalar_one()

    assert row.raw_text == "raw"
    assert row.error_type == "api_error"
    assert row.error_detail == "boom"
