import pytest
from sqlalchemy import select

from core.exceptions import AITransientError
from db.models import Task
from scripts import backfill_russian_text_fields as backfill_script


async def _insert_task(
    db_session_factory,
    *,
    message_id: int,
    raw_text: str | None,
    description: str | None = None,
    outfit: str | None = None,
    notes: str | None = None,
) -> int:
    async with db_session_factory() as session:
        task = Task(
            message_id=message_id,
            chat_id=-100,
            topic_id=777,
            raw_text=raw_text,
            description=description,
            outfit=outfit,
            notes=notes,
            priority="medium",
        )
        session.add(task)
        await session.commit()
        return task.id


async def _fetch_task(db_session_factory, task_id: int) -> Task:
    async with db_session_factory() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        return task


@pytest.mark.asyncio
async def test_backfill_dry_run_does_not_mutate_rows(db_session_factory, monkeypatch):
    task_id = await _insert_task(
        db_session_factory,
        message_id=101,
        raw_text="english brief",
        description="old description",
        outfit="old outfit",
        notes="old notes",
    )

    async def _classify_message(_text, has_photo=False):
        assert has_photo is False
        return {
            "is_task": True,
            "confidence": 0.95,
            "data": {
                "description": "новое описание",
                "outfit": "новый аутфит",
                "notes": "новые заметки",
            },
        }

    monkeypatch.setattr(backfill_script, "classify_message", _classify_message)

    summary = await backfill_script.run_backfill(
        apply=False,
        session_maker=db_session_factory,
    )

    task = await _fetch_task(db_session_factory, task_id)
    assert summary.scanned == 1
    assert summary.changed_candidates == 1
    assert summary.updated == 0
    assert summary.failures == []
    assert task.description == "old description"
    assert task.outfit == "old outfit"
    assert task.notes == "old notes"


@pytest.mark.asyncio
async def test_backfill_apply_updates_text_fields(db_session_factory, monkeypatch):
    task_id = await _insert_task(
        db_session_factory,
        message_id=102,
        raw_text="english brief",
        description="old description",
        outfit="old outfit",
        notes="old notes",
    )

    async def _classify_message(_text, has_photo=False):
        assert has_photo is False
        return {
            "is_task": True,
            "confidence": 0.95,
            "data": {
                "description": "новое описание",
                "outfit": "новый аутфит",
                "notes": "новые заметки",
            },
        }

    monkeypatch.setattr(backfill_script, "classify_message", _classify_message)

    summary = await backfill_script.run_backfill(
        apply=True,
        session_maker=db_session_factory,
    )

    task = await _fetch_task(db_session_factory, task_id)
    assert summary.scanned == 1
    assert summary.changed_candidates == 1
    assert summary.updated == 1
    assert summary.failures == []
    assert task.description == "новое описание"
    assert task.outfit == "новый аутфит"
    assert task.notes == "новые заметки"


@pytest.mark.asyncio
async def test_backfill_best_effort_keeps_processing_after_failure(db_session_factory, monkeypatch):
    failed_task_id = await _insert_task(
        db_session_factory,
        message_id=103,
        raw_text="bad brief",
        description="old one",
    )
    ok_task_id = await _insert_task(
        db_session_factory,
        message_id=104,
        raw_text="good brief",
        description="old two",
        outfit="outfit two",
        notes="notes two",
    )

    async def _classify_message(text, has_photo=False):
        assert has_photo is False
        if "bad brief" in text:
            raise AITransientError("timeout")
        return {
            "is_task": True,
            "confidence": 0.9,
            "data": {
                "description": "описание после бэкфила",
                "outfit": "аутфит после бэкфила",
                "notes": "заметки после бэкфила",
            },
        }

    monkeypatch.setattr(backfill_script, "classify_message", _classify_message)

    summary = await backfill_script.run_backfill(
        apply=True,
        session_maker=db_session_factory,
    )

    failed_task = await _fetch_task(db_session_factory, failed_task_id)
    ok_task = await _fetch_task(db_session_factory, ok_task_id)

    assert summary.scanned == 2
    assert summary.changed_candidates == 1
    assert summary.updated == 1
    assert len(summary.failures) == 1
    assert summary.failures[0].task_id == failed_task_id
    assert "classify_transient" in summary.failures[0].reason
    assert failed_task.description == "old one"
    assert ok_task.description == "описание после бэкфила"
    assert ok_task.outfit == "аутфит после бэкфила"
    assert ok_task.notes == "заметки после бэкфила"


@pytest.mark.asyncio
async def test_backfill_marks_missing_raw_text_as_failed(db_session_factory, monkeypatch):
    task_id = await _insert_task(
        db_session_factory,
        message_id=105,
        raw_text="  ",
        description="old",
    )
    called = {"count": 0}

    async def _classify_message(_text, has_photo=False):
        called["count"] += 1
        return {
            "is_task": True,
            "confidence": 0.9,
            "data": {"description": "new"},
        }

    monkeypatch.setattr(backfill_script, "classify_message", _classify_message)

    summary = await backfill_script.run_backfill(
        apply=True,
        session_maker=db_session_factory,
    )

    task = await _fetch_task(db_session_factory, task_id)
    assert summary.scanned == 1
    assert summary.changed_candidates == 0
    assert summary.updated == 0
    assert len(summary.failures) == 1
    assert summary.failures[0].task_id == task_id
    assert summary.failures[0].reason == "raw_text_missing"
    assert called["count"] == 0
    assert task.description == "old"


@pytest.mark.asyncio
async def test_backfill_marks_non_task_result_as_failed(db_session_factory, monkeypatch):
    task_id = await _insert_task(
        db_session_factory,
        message_id=106,
        raw_text="some text",
        description="old",
    )

    async def _classify_message(_text, has_photo=False):
        assert has_photo is False
        return {"is_task": False, "confidence": 0.99, "reason": "не бриф"}

    monkeypatch.setattr(backfill_script, "classify_message", _classify_message)

    summary = await backfill_script.run_backfill(
        apply=True,
        session_maker=db_session_factory,
    )

    task = await _fetch_task(db_session_factory, task_id)
    assert summary.scanned == 1
    assert summary.changed_candidates == 0
    assert summary.updated == 0
    assert len(summary.failures) == 1
    assert summary.failures[0].task_id == task_id
    assert summary.failures[0].reason == "classify_non_task"
    assert task.description == "old"
