from datetime import datetime, timedelta, timezone

import pytest

from core.config import runtime
from scheduler.jobs import overdue_reminder
from tests.fakes import FakeBot, FakeTask


class _Session:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def test_should_remind_respects_cooldowns():
    now = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)

    t = FakeTask(last_reminder_at=None)
    assert overdue_reminder._should_remind(t, now) is True

    t2 = FakeTask(priority="high", last_reminder_at=(now - timedelta(hours=1)).isoformat())
    runtime.high_urgency_cooldown_hours = 2
    assert overdue_reminder._should_remind(t2, now) is False

    t3 = FakeTask(priority="medium", last_reminder_at="bad-date")
    assert overdue_reminder._should_remind(t3, now) is True


@pytest.mark.asyncio
async def test_check_overdue_and_remind_sends_and_commits(monkeypatch):
    bot = FakeBot()
    session = _Session()

    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    tasks = [
        FakeTask(id=1, priority="high", deadline="2026-02-10", description="a"),
        FakeTask(id=2, priority="medium", deadline="2026-02-11", description="b"),
    ]

    monkeypatch.setattr(overdue_reminder, "today_local", lambda: "2026-02-18")
    monkeypatch.setattr(overdue_reminder.task_repo, "get_overdue_tasks", lambda *_a, **_k: __import__("asyncio").sleep(0, result=tasks))

    await overdue_reminder.check_overdue_and_remind(bot, session)

    assert bot.sent_messages
    assert session.commits == 1
    assert all(task.last_reminder_at for task in tasks)
