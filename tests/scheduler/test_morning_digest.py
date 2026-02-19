import pytest

from core.config import runtime
from scheduler.jobs import morning_digest
from tests.fakes import FakeBot, FakeTask


class _Session:
    async def commit(self):
        return None


def _async_result(result):
    return __import__("asyncio").sleep(0, result=result)


@pytest.mark.asyncio
async def test_send_morning_digest_skips_when_no_active_tasks(monkeypatch):
    bot = FakeBot()
    session = _Session()

    monkeypatch.setattr(morning_digest.task_repo, "get_active_tasks", lambda *_a, **_k: _async_result([]))

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
    monkeypatch.setattr(morning_digest.task_repo, "get_active_tasks", lambda *_a, **_k: _async_result(active))
    monkeypatch.setattr(morning_digest.task_repo, "get_overdue_tasks", lambda *_a, **_k: _async_result([active[0]]))
    monkeypatch.setattr(morning_digest.task_repo, "get_tasks_due_soon", lambda *_a, **_k: _async_result([FakeTask(deadline="2026-02-18")]))
    monkeypatch.setattr(morning_digest.task_repo, "get_finished_tasks_older_than_hours", lambda *_a, **_k: _async_result([]))

    await morning_digest.send_morning_digest(bot, session)

    assert bot.sent_messages
    assert "Утренний дайджест" in bot.sent_messages[0]["text"]


@pytest.mark.asyncio
async def test_digest_includes_overdue_section(monkeypatch):
    bot = FakeBot()
    session = _Session()

    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    overdue_task = FakeTask(id=5, status="processing", amount_total=200, deadline="2026-02-10", description="overdue item")
    active = [overdue_task]

    monkeypatch.setattr(morning_digest, "today_local", lambda: "2026-02-18")
    monkeypatch.setattr(morning_digest.task_repo, "get_active_tasks", lambda *_a, **_k: _async_result(active))
    monkeypatch.setattr(morning_digest.task_repo, "get_overdue_tasks", lambda *_a, **_k: _async_result([overdue_task]))
    monkeypatch.setattr(morning_digest.task_repo, "get_tasks_due_soon", lambda *_a, **_k: _async_result([]))
    monkeypatch.setattr(morning_digest.task_repo, "get_finished_tasks_older_than_hours", lambda *_a, **_k: _async_result([]))

    await morning_digest.send_morning_digest(bot, session)

    text = bot.sent_messages[0]["text"]
    assert "Просроченные" in text
    assert "#005" in text


@pytest.mark.asyncio
async def test_digest_includes_due_today_section(monkeypatch):
    bot = FakeBot()
    session = _Session()

    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    today_task = FakeTask(id=7, status="processing", amount_total=300, deadline="2026-02-18", description="due today")
    active = [today_task]

    monkeypatch.setattr(morning_digest, "today_local", lambda: "2026-02-18")
    monkeypatch.setattr(morning_digest.task_repo, "get_active_tasks", lambda *_a, **_k: _async_result(active))
    monkeypatch.setattr(morning_digest.task_repo, "get_overdue_tasks", lambda *_a, **_k: _async_result([]))
    monkeypatch.setattr(morning_digest.task_repo, "get_tasks_due_soon", lambda *_a, **_k: _async_result([today_task]))
    monkeypatch.setattr(morning_digest.task_repo, "get_finished_tasks_older_than_hours", lambda *_a, **_k: _async_result([]))

    await morning_digest.send_morning_digest(bot, session)

    text = bot.sent_messages[0]["text"]
    assert "Дедлайн сегодня" in text
    assert "#007" in text


@pytest.mark.asyncio
async def test_digest_includes_finished_not_delivered_section(monkeypatch):
    bot = FakeBot()
    session = _Session()

    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777
    runtime.finished_reminder_hours = 24

    finished_task = FakeTask(id=9, status="finished", description="finished item")
    active = [finished_task]

    monkeypatch.setattr(morning_digest, "today_local", lambda: "2026-02-18")
    monkeypatch.setattr(morning_digest.task_repo, "get_active_tasks", lambda *_a, **_k: _async_result(active))
    monkeypatch.setattr(morning_digest.task_repo, "get_overdue_tasks", lambda *_a, **_k: _async_result([]))
    monkeypatch.setattr(morning_digest.task_repo, "get_tasks_due_soon", lambda *_a, **_k: _async_result([]))
    monkeypatch.setattr(morning_digest.task_repo, "get_finished_tasks_older_than_hours", lambda *_a, **_k: _async_result([finished_task]))

    await morning_digest.send_morning_digest(bot, session)

    text = bot.sent_messages[0]["text"]
    assert "Отснято, но не доставлено" in text
    assert "#009" in text


@pytest.mark.asyncio
async def test_digest_section_limit_caps_entries(monkeypatch):
    bot = FakeBot()
    session = _Session()

    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    overdue_tasks = [
        FakeTask(id=i, status="processing", amount_total=100, deadline="2026-02-01", description=f"task {i}")
        for i in range(1, 16)
    ]
    active = overdue_tasks

    monkeypatch.setattr(morning_digest, "today_local", lambda: "2026-02-18")
    monkeypatch.setattr(morning_digest.task_repo, "get_active_tasks", lambda *_a, **_k: _async_result(active))
    monkeypatch.setattr(morning_digest.task_repo, "get_overdue_tasks", lambda *_a, **_k: _async_result(overdue_tasks))
    monkeypatch.setattr(morning_digest.task_repo, "get_tasks_due_soon", lambda *_a, **_k: _async_result([]))
    monkeypatch.setattr(morning_digest.task_repo, "get_finished_tasks_older_than_hours", lambda *_a, **_k: _async_result([]))

    await morning_digest.send_morning_digest(bot, session)

    text = bot.sent_messages[0]["text"]
    assert "... и ещё 5" in text
