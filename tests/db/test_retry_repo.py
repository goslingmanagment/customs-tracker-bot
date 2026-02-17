from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from db.models import AIRetryQueue
from db.repo import retry_repo


@pytest.mark.asyncio
async def test_enqueue_insert_and_update_existing_row(db_session):
    row = await retry_repo.enqueue_ai_retry(
        db_session,
        chat_id=-100,
        message_id=10,
        topic_id=777,
        raw_text="hello",
        has_photo=False,
        sender_username="u1",
        error_detail="E1",
    )
    assert row.attempt_count == 0

    updated = await retry_repo.enqueue_ai_retry(
        db_session,
        chat_id=-100,
        message_id=10,
        topic_id=888,
        raw_text="hello-2",
        has_photo=True,
        sender_username="u2",
        error_detail="E2",
    )

    assert updated.id == row.id
    assert updated.topic_id == 888
    assert updated.raw_text == "hello-2"
    assert updated.has_photo is True
    assert updated.sender_username == "u2"
    assert updated.last_error == "E2"


@pytest.mark.asyncio
async def test_get_due_retries_ordering_and_limit(db_session):
    now = datetime.now(timezone.utc)

    await retry_repo.enqueue_ai_retry(
        db_session,
        chat_id=1,
        message_id=1,
        topic_id=None,
        raw_text="a",
        has_photo=False,
        next_retry_at=(now - timedelta(minutes=2)).isoformat(),
    )
    await retry_repo.enqueue_ai_retry(
        db_session,
        chat_id=1,
        message_id=2,
        topic_id=None,
        raw_text="b",
        has_photo=False,
        next_retry_at=(now - timedelta(minutes=1)).isoformat(),
    )
    await retry_repo.enqueue_ai_retry(
        db_session,
        chat_id=1,
        message_id=3,
        topic_id=None,
        raw_text="c",
        has_photo=False,
        next_retry_at=(now + timedelta(minutes=1)).isoformat(),
    )

    due = await retry_repo.get_due_ai_retries(db_session, now_iso=now.isoformat(), limit=1)
    assert len(due) == 1
    assert due[0].message_id == 1


@pytest.mark.asyncio
async def test_reschedule_and_delete_retry(db_session):
    row = await retry_repo.enqueue_ai_retry(
        db_session,
        chat_id=-1,
        message_id=99,
        topic_id=777,
        raw_text="z",
        has_photo=False,
    )

    await retry_repo.reschedule_ai_retry(
        db_session,
        row,
        attempt_count=3,
        next_retry_at="2026-02-18T00:00:00+00:00",
        last_error="timeout",
    )

    found = await retry_repo.get_ai_retry_by_id(db_session, row.id)
    assert found is not None
    assert found.attempt_count == 3
    assert found.last_error == "timeout"

    await retry_repo.delete_ai_retry(db_session, found)

    deleted = (
        await db_session.execute(select(AIRetryQueue).where(AIRetryQueue.id == row.id))
    ).scalar_one_or_none()
    assert deleted is None
