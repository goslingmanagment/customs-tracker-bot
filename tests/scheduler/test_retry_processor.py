from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.config import runtime
from core.exceptions import AITransientError
from scheduler.jobs import retry_processor
from tests.fakes import FakeBot, FakeTask


class _Session:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _row(**kwargs):
    base = {
        "id": 1,
        "chat_id": -100,
        "message_id": 101,
        "topic_id": 777,
        "raw_text": "text",
        "has_photo": False,
        "sender_username": "u",
        "attempt_count": 0,
        "first_enqueued_at": datetime.now(timezone.utc).isoformat(),
        "next_retry_at": datetime.now(timezone.utc).isoformat(),
        "last_error": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_parse_iso_timestamp():
    assert retry_processor._parse_iso_timestamp(None) is None
    assert retry_processor._parse_iso_timestamp("bad") is None
    assert retry_processor._parse_iso_timestamp("2026-02-18T10:00:00+00:00") is not None


@pytest.mark.asyncio
async def test_reschedule_or_fail_exhausted(monkeypatch):
    session = _Session()
    bot = FakeBot()
    now = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)

    row = _row(
        id=10,
        attempt_count=4,
        first_enqueued_at=(now - timedelta(hours=3)).isoformat(),
    )

    flags = {"parse_failure": False, "marked": False, "deleted": False, "alert": False}

    monkeypatch.setattr(retry_processor.retry_repo, "get_ai_retry_by_id", lambda *_a, **_k: __import__("asyncio").sleep(0, result=row))

    async def _log_pf(*_args, **_kwargs):
        flags["parse_failure"] = True

    async def _mark(*_args, **_kwargs):
        flags["marked"] = True

    async def _delete(*_args, **_kwargs):
        flags["deleted"] = True

    async def _alert(*_args, **_kwargs):
        flags["alert"] = True

    monkeypatch.setattr(retry_processor.message_repo, "log_parse_failure", _log_pf)
    monkeypatch.setattr(retry_processor.message_repo, "mark_message_processed", _mark)
    monkeypatch.setattr(retry_processor.retry_repo, "delete_ai_retry", _delete)
    monkeypatch.setattr(retry_processor, "_send_retry_exhausted_alert", _alert)

    await retry_processor._reschedule_or_fail(
        session,
        bot,
        queue_id=10,
        now=now,
        error_message="boom",
    )

    assert all(flags.values())
    assert session.commits == 1


@pytest.mark.asyncio
async def test_reschedule_or_fail_reschedules(monkeypatch):
    session = _Session()
    bot = FakeBot()
    now = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)
    row = _row(id=11, attempt_count=0, first_enqueued_at=now.isoformat())

    captured = {}

    monkeypatch.setattr(retry_processor.retry_repo, "get_ai_retry_by_id", lambda *_a, **_k: __import__("asyncio").sleep(0, result=row))

    async def _reschedule(_session, _row_obj, *, attempt_count, next_retry_at, last_error):
        captured["attempt_count"] = attempt_count
        captured["next_retry_at"] = next_retry_at
        captured["last_error"] = last_error

    monkeypatch.setattr(retry_processor.retry_repo, "reschedule_ai_retry", _reschedule)

    await retry_processor._reschedule_or_fail(
        session,
        bot,
        queue_id=11,
        now=now,
        error_message="temp",
    )

    assert captured["attempt_count"] == 1
    assert captured["last_error"] == "temp"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_process_single_retry_already_processed(monkeypatch):
    session = _Session()
    bot = FakeBot()
    row = _row(id=20)

    deleted = {"value": False}

    monkeypatch.setattr(retry_processor.retry_repo, "get_ai_retry_by_id", lambda *_a, **_k: __import__("asyncio").sleep(0, result=row))
    monkeypatch.setattr(retry_processor.message_repo, "is_message_processed", lambda *_a, **_k: __import__("asyncio").sleep(0, result=True))

    async def _delete(*_args, **_kwargs):
        deleted["value"] = True

    monkeypatch.setattr(retry_processor.retry_repo, "delete_ai_retry", _delete)

    await retry_processor._process_single_retry(bot, row.id, session)

    assert deleted["value"] is True
    assert session.commits == 1


@pytest.mark.asyncio
async def test_process_single_retry_success_creates_task(monkeypatch):
    session = _Session()
    bot = FakeBot()
    row = _row(id=21)
    runtime.ai_confidence_threshold = 0.7

    task = FakeTask(id=9, chat_id=row.chat_id, topic_id=row.topic_id)
    flags = {"bound": False, "marked": False, "deleted": False}

    monkeypatch.setattr(retry_processor.retry_repo, "get_ai_retry_by_id", lambda *_a, **_k: __import__("asyncio").sleep(0, result=row))
    monkeypatch.setattr(retry_processor.message_repo, "is_message_processed", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))
    monkeypatch.setattr(retry_processor.task_repo, "get_task_by_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result=None))
    monkeypatch.setattr(retry_processor, "classify_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result={"is_task": True, "confidence": 0.9, "data": {}}))
    monkeypatch.setattr(retry_processor, "sanitize_ai_data", lambda data: data)
    monkeypatch.setattr(retry_processor, "build_task_kwargs", lambda *args, **kwargs: {})
    monkeypatch.setattr(retry_processor.task_repo, "create_task", lambda *_a, **_k: __import__("asyncio").sleep(0, result=(task, True)))
    monkeypatch.setattr(retry_processor, "build_draft_card", lambda _task: ("card", None))

    async def _bind(_session, _task, _mid):
        flags["bound"] = True

    async def _mark(*_args, **_kwargs):
        flags["marked"] = True

    async def _delete(*_args, **_kwargs):
        flags["deleted"] = True

    monkeypatch.setattr(retry_processor.task_repo, "update_task_bot_message_id", _bind)
    monkeypatch.setattr(retry_processor.message_repo, "mark_message_processed", _mark)
    monkeypatch.setattr(retry_processor.retry_repo, "delete_ai_retry", _delete)

    await retry_processor._process_single_retry(bot, row.id, session)

    assert bot.sent_messages
    assert all(flags.values())
    assert session.commits == 1


@pytest.mark.asyncio
async def test_process_ai_retry_queue_iterates_rows(monkeypatch):
    session = _Session()
    bot = FakeBot()
    rows = [_row(id=1), _row(id=2)]

    processed = []

    monkeypatch.setattr(retry_processor.retry_repo, "get_due_ai_retries", lambda *_a, **_k: __import__("asyncio").sleep(0, result=rows))

    async def _process(_bot, queue_id, _session):
        processed.append(queue_id)
        if queue_id == 2:
            raise RuntimeError("boom")

    monkeypatch.setattr(retry_processor, "_process_single_retry", _process)

    await retry_processor.process_ai_retry_queue(bot, session)

    assert processed == [1, 2]
