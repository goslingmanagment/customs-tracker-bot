from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from core.exceptions import InvalidTransitionError
from db.models import StatusLog, Task
from db.repo import task_repo


def _kwargs(message_id: int, *, chat_id: int = -1001, status: str = "draft", deadline: str | None = None):
    return {
        "message_id": message_id,
        "chat_id": chat_id,
        "topic_id": 777,
        "raw_text": "raw",
        "description": f"task-{message_id}",
        "priority": "medium",
        "status": status,
        "deadline": deadline,
        "ai_confidence": 0.9,
    }


@pytest.mark.asyncio
async def test_create_task_creates_status_log_and_duplicate_recovery(db_session):
    task, created = await task_repo.create_task(db_session, **_kwargs(1))
    await db_session.commit()

    assert created is True
    assert task.id > 0

    logs = (await db_session.execute(select(StatusLog).where(StatusLog.task_id == task.id))).scalars().all()
    assert len(logs) == 1
    assert logs[0].from_status is None
    assert logs[0].to_status == "draft"
    assert logs[0].note == "auto-detected"

    dup, dup_created = await task_repo.create_task(db_session, **_kwargs(1))
    assert dup_created is False
    assert dup.id == task.id


@pytest.mark.asyncio
async def test_update_task_status_validates_transitions(db_session):
    task, _ = await task_repo.create_task(db_session, **_kwargs(2))

    await task_repo.update_task_status(db_session, task, "awaiting_confirmation", changed_by_name="admin")
    await task_repo.update_task_status(db_session, task, "processing", changed_by_name="model")
    await task_repo.update_task_status(db_session, task, "finished", changed_by_name="model")

    assert task.status == "finished"
    assert task.finished_at is not None
    assert task.delivered_at is None

    await task_repo.update_task_status(db_session, task, "delivered", changed_by_name="admin")
    assert task.status == "delivered"
    assert task.finished_at is not None
    assert task.delivered_at is not None


@pytest.mark.asyncio
async def test_update_task_status_raises_for_invalid_transition(db_session):
    task, _ = await task_repo.create_task(db_session, **_kwargs(3))

    with pytest.raises(InvalidTransitionError):
        await task_repo.update_task_status(db_session, task, "delivered")


@pytest.mark.asyncio
async def test_force_update_task_status_and_metadata_updates(db_session):
    task, _ = await task_repo.create_task(db_session, **_kwargs(4))
    await task_repo.force_update_task_status(db_session, task, "cancelled", changed_by_name="admin")

    assert task.status == "cancelled"
    logs = (await db_session.execute(select(StatusLog).where(StatusLog.task_id == task.id))).scalars().all()
    assert any(log.note == "forced_status_update" for log in logs)


@pytest.mark.asyncio
async def test_update_deadline_priority_and_bot_message_id(db_session):
    task, _ = await task_repo.create_task(db_session, **_kwargs(5))

    await task_repo.update_task_bot_message_id(db_session, task, 999)
    await task_repo.update_task_deadline(db_session, task, "2026-02-20", changed_by_name="lead")
    await task_repo.update_task_priority(db_session, task, "high", changed_by_name="lead")

    assert task.bot_message_id == 999
    assert task.deadline == "2026-02-20"
    assert task.priority == "high"

    logs = (await db_session.execute(select(StatusLog).where(StatusLog.task_id == task.id))).scalars().all()
    notes = [log.note for log in logs if log.note]
    assert any("deadline:" in note for note in notes)
    assert any("priority:" in note for note in notes)


@pytest.mark.asyncio
async def test_task_queries_by_status_and_deadline(db_session):
    t1, _ = await task_repo.create_task(db_session, **_kwargs(10, status="draft", deadline="2026-02-10"))
    t2, _ = await task_repo.create_task(
        db_session, **_kwargs(11, status="processing", deadline="2026-02-15")
    )
    t3, _ = await task_repo.create_task(
        db_session, **_kwargs(12, status="finished", deadline="2026-02-08")
    )
    t4, _ = await task_repo.create_task(
        db_session, **_kwargs(13, status="delivered", deadline="2026-02-09")
    )
    t5, _ = await task_repo.create_task(
        db_session, **_kwargs(14, status="cancelled", deadline="2026-02-07")
    )
    assert all([t1, t2, t3, t4, t5])

    active = await task_repo.get_active_tasks(db_session)
    assert {t.status for t in active} == {"draft", "processing", "finished"}

    overdue = await task_repo.get_overdue_tasks(db_session, today="2026-02-12")
    assert {t.id for t in overdue} == {t1.id}

    due_soon = await task_repo.get_tasks_due_soon(db_session, days=3, today="2026-02-12")
    assert {t.id for t in due_soon} == {t2.id}

    all_tasks = await task_repo.get_all_tasks(db_session)
    assert len(all_tasks) == 5


@pytest.mark.asyncio
async def test_get_finished_tasks_older_than_hours_handles_invalid_timestamps(db_session, freeze_time):
    now = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)
    freeze_time(task_repo, now)

    old_task, _ = await task_repo.create_task(db_session, **_kwargs(20, status="finished"))
    old_task.finished_at = "2026-02-17T08:00:00+00:00"

    fresh_task, _ = await task_repo.create_task(db_session, **_kwargs(21, status="finished"))
    fresh_task.finished_at = "2026-02-18T11:30:00+00:00"

    broken_task, _ = await task_repo.create_task(db_session, **_kwargs(22, status="finished"))
    broken_task.finished_at = "not-a-date"

    overdue = await task_repo.get_finished_tasks_older_than_hours(db_session, 2)
    assert {task.id for task in overdue} == {old_task.id}


@pytest.mark.asyncio
async def test_delete_task_removes_row(db_session):
    task, _ = await task_repo.create_task(db_session, **_kwargs(30))
    await task_repo.delete_task(db_session, task)

    row = (await db_session.execute(select(Task).where(Task.id == task.id))).scalar_one_or_none()
    assert row is None
