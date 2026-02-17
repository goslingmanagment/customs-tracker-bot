from types import SimpleNamespace

import pytest

from handlers import messages
from tests.fakes import FakeMessage, FakeSessionFactory, FakeTask, make_user


class _Session:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def test_is_command():
    assert messages._is_command(FakeMessage(text="/start")) is True
    assert messages._is_command(FakeMessage(text="hello")) is False


@pytest.mark.asyncio
async def test_handle_customs_message_skips_real_replies(monkeypatch):
    replied = FakeMessage(text="parent", message_id=500)
    msg = FakeMessage(text="reply", reply_to_message=replied, topic_id=777)

    called = {"pending": False}

    async def _pending(_message):
        called["pending"] = True
        return False

    monkeypatch.setattr(messages, "is_topic_root_reply", lambda _m: False)
    monkeypatch.setattr(messages, "maybe_process_pending_postpone", _pending)

    await messages.handle_customs_message(msg)

    assert called["pending"] is False


@pytest.mark.asyncio
async def test_handle_customs_message_processes_when_not_processed(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="brief text")

    called = {"process": False}

    async def _is_processed(*_args, **_kwargs):
        return False

    async def _process(_message, _session):
        called["process"] = True

    async def _pending(_message):
        return False

    monkeypatch.setattr(messages, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(messages.message_repo, "is_message_processed", _is_processed)
    monkeypatch.setattr(messages, "process_brief", _process)
    monkeypatch.setattr(messages, "maybe_process_pending_postpone", _pending)

    await messages.handle_customs_message(msg)

    assert called["process"] is True


@pytest.mark.asyncio
async def test_handle_customs_message_skips_already_processed(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="brief text")

    async def _is_processed(*_args, **_kwargs):
        return True

    called = {"process": False}

    async def _process(*_args, **_kwargs):
        called["process"] = True

    monkeypatch.setattr(messages, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(messages.message_repo, "is_message_processed", _is_processed)
    monkeypatch.setattr(messages, "process_brief", _process)
    monkeypatch.setattr(messages, "maybe_process_pending_postpone", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))

    await messages.handle_customs_message(msg)

    assert called["process"] is False


@pytest.mark.asyncio
async def test_handle_edited_message_not_linked_reprocesses(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="edited text")

    called = {"process": False}

    async def _get_task(*_args, **_kwargs):
        return None

    async def _process(*_args, **_kwargs):
        called["process"] = True

    monkeypatch.setattr(messages, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(messages.task_repo, "get_task_by_message", _get_task)
    monkeypatch.setattr(messages, "process_brief", _process)

    await messages.handle_edited_message(msg)

    assert called["process"] is True


@pytest.mark.asyncio
async def test_handle_edited_message_updates_existing_task(monkeypatch):
    session = _Session()
    bot = __import__("tests.fakes", fromlist=["FakeBot"]).FakeBot()
    msg = FakeMessage(text="updated text", bot=bot, from_user=make_user(5, "editor"))

    task = FakeTask(
        id=11,
        chat_id=msg.chat.id,
        topic_id=msg.message_thread_id,
        message_id=msg.message_id,
        bot_message_id=888,
        description="old",
    )

    async def _get_task(*_args, **_kwargs):
        return task

    async def _classify(*_args, **_kwargs):
        return {
            "is_task": True,
            "confidence": 0.91,
            "data": {"description": "new desc", "priority": "high", "deadline": "2026-02-20"},
        }

    monkeypatch.setattr(messages, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(messages.task_repo, "get_task_by_message", _get_task)
    monkeypatch.setattr(messages, "classify_message", _classify)
    monkeypatch.setattr(messages, "get_card_for_status", lambda _task: ("card", None))

    await messages.handle_edited_message(msg)

    assert task.description == "new desc"
    assert task.priority == "high"
    assert task.deadline == "2026-02-20"
    assert bot.edited_texts and bot.edited_texts[0]["message_id"] == 888
