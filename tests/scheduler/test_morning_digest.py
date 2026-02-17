import pytest

from core.config import runtime
from scheduler.jobs import morning_digest
from tests.fakes import FakeBot, FakeTask


class _Session:
    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_send_morning_digest_skips_when_no_active_tasks(monkeypatch):
    bot = FakeBot()
    session = _Session()

    monkeypatch.setattr(morning_digest.task_repo, "get_active_tasks", lambda *_a, **_k: __import__("asyncio").sleep(0, result=[]))

    await morning_digest.send_morning_digest(bot, session)

    assert bot.sent_messages == []


@pytest.mark.asyncio
async def test_send_morning_digest_sends_summary(monkeypatch):
    bot = FakeBot()
    session = _Session()

    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    active = [
        FakeTask(id=1, status="draft", amount_total=50),
        FakeTask(id=2, status="processing", amount_total=100),
        FakeTask(id=3, status="finished", amount_total=150),
    ]

    monkeypatch.setattr(morning_digest, "today_local", lambda: "2026-02-18")
    monkeypatch.setattr(morning_digest.task_repo, "get_active_tasks", lambda *_a, **_k: __import__("asyncio").sleep(0, result=active))
    monkeypatch.setattr(morning_digest.task_repo, "get_overdue_tasks", lambda *_a, **_k: __import__("asyncio").sleep(0, result=[active[0]]))
    monkeypatch.setattr(morning_digest.task_repo, "get_tasks_due_soon", lambda *_a, **_k: __import__("asyncio").sleep(0, result=[FakeTask(deadline="2026-02-18")]))

    await morning_digest.send_morning_digest(bot, session)

    assert bot.sent_messages
    assert "Утренний дайджест" in bot.sent_messages[0]["text"]
