from datetime import datetime, timedelta, timezone

import pytest

from core.config import runtime
from scheduler.jobs import deadline_reminder
from tests.fakes import FakeBot, FakeTask


class _Session:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def test_should_remind_handles_bad_timestamps():
    now = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)

    assert deadline_reminder._should_remind(FakeTask(last_reminder_at=None), now) is True
    assert deadline_reminder._should_remind(FakeTask(last_reminder_at="bad"), now) is True

    task = FakeTask(priority="medium", last_reminder_at=(now - timedelta(hours=1)).isoformat())
    runtime.overdue_reminder_cooldown_hours = 4
    assert deadline_reminder._should_remind(task, now) is False


@pytest.mark.asyncio
async def test_check_upcoming_deadlines_uses_reminder_days(monkeypatch):
    bot = FakeBot()
    session = _Session()

    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777
    runtime.reminder_hours_before = 25

    captured = {}
    tasks = [FakeTask(id=1, deadline="2026-02-19", description="soon")]

    async def _get_due(_session, days, today):
        captured["days"] = days
        captured["today"] = today
        return tasks

    monkeypatch.setattr(deadline_reminder, "today_local", lambda: "2026-02-18")
    monkeypatch.setattr(deadline_reminder.task_repo, "get_tasks_due_soon", _get_due)

    await deadline_reminder.check_upcoming_deadlines(bot, session)

    assert captured["days"] == 2
    assert bot.sent_messages
    assert session.commits == 1
