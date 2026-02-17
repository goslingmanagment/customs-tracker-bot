from types import SimpleNamespace

import pytest

from handlers import replies
from tests.fakes import FakeMessage, FakeSessionFactory, FakeTask, make_user


class _Session:
    async def commit(self):
        return None


def test_looks_like_delivery_report_keyword():
    assert replies.looks_like_delivery_report("Отправлено") is True
    assert replies.looks_like_delivery_report("random text") is False


@pytest.mark.asyncio
async def test_handle_reply_topic_root_falls_back_to_brief(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="brief", reply_to_message=FakeMessage(text="root", message_id=777), topic_id=777)

    called = {"process": False}

    monkeypatch.setattr(replies, "is_topic_root_reply", lambda _m: True)
    monkeypatch.setattr(replies, "maybe_process_pending_postpone", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))

    async def _process(*_args, **_kwargs):
        called["process"] = True

    monkeypatch.setattr(replies, "process_brief", _process)
    monkeypatch.setattr(replies, "async_session", FakeSessionFactory(session))

    await replies.handle_reply(msg)

    assert called["process"] is True


@pytest.mark.asyncio
async def test_handle_reply_prompts_shot_confirmation(monkeypatch):
    session = _Session()
    parent = FakeMessage(text="task source", message_id=900)
    msg = FakeMessage(
        text="готово",
        reply_to_message=parent,
        from_user=make_user(7, "model"),
    )
    task = FakeTask(id=5, status="processing", message_id=900)

    async def _get_by_message(*_args, **_kwargs):
        return task

    monkeypatch.setattr(replies, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(replies.task_repo, "get_task_by_message", _get_by_message)
    monkeypatch.setattr(replies.task_repo, "get_task_by_bot_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result=None))
    monkeypatch.setattr(replies, "is_detection_actor", lambda _u: True)
    monkeypatch.setattr(replies, "resolve_known_roles", lambda *_a, **_k: __import__("asyncio").sleep(0))

    await replies.handle_reply(msg)

    assert msg.replies and "Отчёт о съёмке" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_handle_reply_prompts_delivery_confirmation(monkeypatch):
    session = _Session()
    parent = FakeMessage(text="task source", message_id=901)
    msg = FakeMessage(
        text="доставлено",
        reply_to_message=parent,
        from_user=make_user(8, "lead"),
    )
    task = FakeTask(id=6, status="finished", message_id=901)

    async def _get_by_message(*_args, **_kwargs):
        return task

    monkeypatch.setattr(replies, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(replies.task_repo, "get_task_by_message", _get_by_message)
    monkeypatch.setattr(replies.task_repo, "get_task_by_bot_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result=None))
    monkeypatch.setattr(replies, "is_detection_actor", lambda _u: True)
    monkeypatch.setattr(replies, "is_admin_or_teamlead", lambda _u: True)
    monkeypatch.setattr(replies, "resolve_known_roles", lambda *_a, **_k: __import__("asyncio").sleep(0))

    await replies.handle_reply(msg)

    assert msg.replies and "доставлен фану" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_handle_reply_to_bot_message_runs_deadline_fallback(monkeypatch):
    session = _Session()
    bot_user = make_user(999, "bot", is_bot=True)
    parent = FakeMessage(text="card", message_id=800, from_user=bot_user)
    msg = FakeMessage(text="05.03", reply_to_message=parent, from_user=make_user(1, "lead"))

    task = FakeTask(id=3, status="processing", bot_message_id=800)
    called = {"deadline": False}

    async def _get_by_message(*_args, **_kwargs):
        return task

    async def _process_deadline(*_args, **_kwargs):
        called["deadline"] = True
        return "updated"

    monkeypatch.setattr(replies, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(replies.task_repo, "get_task_by_message", _get_by_message)
    monkeypatch.setattr(replies, "is_detection_actor", lambda _u: False)
    monkeypatch.setattr(replies, "process_deadline_change_text", _process_deadline)

    await replies.handle_reply(msg)

    assert called["deadline"] is True


@pytest.mark.asyncio
async def test_handle_reply_without_task_falls_back_to_brief(monkeypatch):
    session = _Session()
    parent = FakeMessage(text="parent", message_id=700)
    msg = FakeMessage(text="not linked", reply_to_message=parent)

    called = {"brief": False}

    monkeypatch.setattr(replies, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(replies.task_repo, "get_task_by_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result=None))
    monkeypatch.setattr(replies.task_repo, "get_task_by_bot_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result=None))
    monkeypatch.setattr(replies.message_repo, "is_message_processed", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))

    async def _process(*_args, **_kwargs):
        called["brief"] = True

    monkeypatch.setattr(replies, "process_brief", _process)

    await replies.handle_reply(msg)

    assert called["brief"] is True
