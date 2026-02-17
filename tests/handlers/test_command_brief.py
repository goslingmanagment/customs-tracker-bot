import pytest

from core.exceptions import AITransientError
from handlers.commands import brief
from tests.fakes import FakeMessage, FakeSessionFactory, FakeTask, make_user


class _Session:
    async def commit(self):
        return None

    async def rollback(self):
        return None


@pytest.mark.asyncio
async def test_cmd_add_denies_user_without_permission(monkeypatch):
    msg = FakeMessage(text="/add", from_user=make_user(1, "user"))

    monkeypatch.setattr(brief, "can_add_brief", lambda _u: False)

    await brief.cmd_add(msg)

    assert msg.replies and "Только администраторы" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_add_requires_reply(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="/add", from_user=make_user(1, "admin"), reply_to_message=None)

    monkeypatch.setattr(brief, "can_add_brief", lambda _u: True)
    monkeypatch.setattr(brief, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(brief, "resolve_known_roles", lambda *_a, **_k: __import__("asyncio").sleep(0))

    await brief.cmd_add(msg)

    assert msg.replies and "ответ на сообщение" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_add_reports_existing_task(monkeypatch):
    session = _Session()
    replied = FakeMessage(text="brief source", message_id=400, chat_id=-100, topic_id=777)
    msg = FakeMessage(text="/add", from_user=make_user(1, "admin"), reply_to_message=replied)

    monkeypatch.setattr(brief, "can_add_brief", lambda _u: True)
    monkeypatch.setattr(brief, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(brief, "resolve_known_roles", lambda *_a, **_k: __import__("asyncio").sleep(0))
    monkeypatch.setattr(brief.task_repo, "get_task_by_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result=FakeTask(id=77)))

    await brief.cmd_add(msg)

    assert msg.replies and "#077" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_add_handles_transient_ai_error(monkeypatch):
    session = _Session()
    replied = FakeMessage(text="brief source", message_id=401, chat_id=-100, topic_id=777)
    msg = FakeMessage(text="/add", from_user=make_user(1, "admin"), reply_to_message=replied)

    monkeypatch.setattr(brief, "can_add_brief", lambda _u: True)
    monkeypatch.setattr(brief, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(brief, "resolve_known_roles", lambda *_a, **_k: __import__("asyncio").sleep(0))
    monkeypatch.setattr(brief.task_repo, "get_task_by_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result=None))
    monkeypatch.setattr(brief, "evaluate_brief_env_readiness", lambda: __import__("types").SimpleNamespace(ready=True, blockers=[], warnings=[]))

    async def _classify(*_args, **_kwargs):
        raise AITransientError("boom")

    monkeypatch.setattr(brief, "classify_message", _classify)

    await brief.cmd_add(msg)

    assert msg.replies and "Ошибка AI" in msg.replies[0][0]
