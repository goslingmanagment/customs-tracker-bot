import pytest

from handlers.commands import tasks
from tests.fakes import FakeMessage, FakeSessionFactory, FakeTask, make_user


class _Session:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_cmd_task_usage_and_validation():
    msg_missing = FakeMessage(text="/task")
    await tasks.cmd_task(msg_missing)
    assert "Использование" in msg_missing.replies[0][0]

    msg_bad = FakeMessage(text="/task abc")
    await tasks.cmd_task(msg_bad)
    assert "должен быть числом" in msg_bad.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_task_not_found(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="/task 5")

    monkeypatch.setattr(tasks, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(tasks.task_repo, "get_task_by_id", lambda *_a, **_k: __import__("asyncio").sleep(0, result=None))

    await tasks.cmd_task(msg)

    assert msg.replies and "не найдена" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_revert_denies_non_admin(monkeypatch):
    msg = FakeMessage(text="/revert 1", from_user=make_user(2, "user"))
    monkeypatch.setattr(tasks, "is_admin", lambda _u: False)

    await tasks.cmd_revert(msg)

    assert msg.replies and "только администраторам" in msg.replies[0][0].lower()


@pytest.mark.asyncio
async def test_cmd_revert_success(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="/revert 5", from_user=make_user(1, "admin"))

    task = FakeTask(id=5, status="processing")

    monkeypatch.setattr(tasks, "is_admin", lambda _u: True)
    monkeypatch.setattr(tasks, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(tasks, "resolve_admin_identity", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))
    monkeypatch.setattr(tasks.task_repo, "get_task_by_id", lambda *_a, **_k: __import__("asyncio").sleep(0, result=task))
    monkeypatch.setattr(tasks.task_repo, "force_update_task_status", lambda *_a, **_k: __import__("asyncio").sleep(0, result=task))
    monkeypatch.setattr(tasks, "_refresh_task_card", lambda *_a, **_k: __import__("asyncio").sleep(0, result=True))

    await tasks.cmd_revert(msg)

    assert session.commits == 1
    assert msg.replies and "возвращён назад" in msg.replies[0][0]
