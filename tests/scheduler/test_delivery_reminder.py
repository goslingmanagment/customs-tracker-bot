from datetime import datetime, timedelta, timezone

import pytest

from core.config import runtime
from scheduler.jobs import delivery_reminder
from tests.fakes import FakeBot, FakeTask


class _Session:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def test_should_remind_delivery_respects_cooldown():
    now = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)
    runtime.overdue_reminder_cooldown_hours = 4

    task = FakeTask(last_reminder_at=(now - timedelta(hours=1)).isoformat())
    assert delivery_reminder._should_remind(task, now) is False


@pytest.mark.asyncio
async def test_check_finished_pending_delivery(monkeypatch):
    bot = FakeBot()
    session = _Session()

    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777
    runtime.finished_reminder_hours = 24

    tasks = [FakeTask(id=9), FakeTask(id=10)]

    monkeypatch.setattr(
        delivery_reminder.task_repo,
        "get_finished_tasks_older_than_hours",
        lambda *_a, **_k: __import__("asyncio").sleep(0, result=tasks),
    )

    await delivery_reminder.check_finished_pending_delivery(bot, session)

    assert bot.sent_messages
    assert session.commits == 1
    assert all(t.last_reminder_at for t in tasks)
