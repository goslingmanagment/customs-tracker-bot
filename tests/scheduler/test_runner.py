from datetime import datetime, timezone

import pytest

from core.config import runtime
from scheduler import runner
from tests.fakes import FakeBot, FakeSessionFactory


class _Session:
    async def commit(self):
        return None


def test_local_now_falls_back_to_utc():
    runtime.timezone = "No/SuchTimezone"
    value = runner._local_now()
    assert value.tzinfo is not None


@pytest.mark.asyncio
async def test_start_scheduler_runs_jobs_and_exits_on_cancel(monkeypatch):
    bot = FakeBot()
    session = _Session()

    calls = {
        "retry": 0,
        "overdue": 0,
        "deadlines": 0,
        "delivery": 0,
        "digest": 0,
    }

    async def _retry(*_args, **_kwargs):
        calls["retry"] += 1

    async def _overdue(*_args, **_kwargs):
        calls["overdue"] += 1

    async def _deadlines(*_args, **_kwargs):
        calls["deadlines"] += 1

    async def _delivery(*_args, **_kwargs):
        calls["delivery"] += 1

    async def _digest(*_args, **_kwargs):
        calls["digest"] += 1

    monkeypatch.setattr(runner, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(runner, "process_ai_retry_queue", _retry)
    monkeypatch.setattr(runner, "check_overdue_and_remind", _overdue)
    monkeypatch.setattr(runner, "check_upcoming_deadlines", _deadlines)
    monkeypatch.setattr(runner, "check_finished_pending_delivery", _delivery)
    monkeypatch.setattr(runner, "send_morning_digest", _digest)
    monkeypatch.setattr(runner, "_local_now", lambda: datetime(2026, 2, 18, runner.MORNING_DIGEST_HOUR, 0, tzinfo=timezone.utc))

    async def _sleep(_seconds):
        raise __import__("asyncio").CancelledError()

    monkeypatch.setattr(runner.asyncio, "sleep", _sleep)

    with pytest.raises(__import__("asyncio").CancelledError):
        await runner.start_scheduler(bot)

    assert calls["retry"] == 1
    assert calls["overdue"] == 1
    assert calls["deadlines"] == 1
    assert calls["delivery"] == 1
    assert calls["digest"] == 1
