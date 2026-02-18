import pytest

from handlers import callbacks
from tests.fakes import FakeCallbackQuery, FakeSessionFactory, FakeTask, make_user


class _Session:
    def __init__(self, *, pending: bool = False):
        self.commits = 0
        self.new = {object()} if pending else set()
        self.dirty = set()
        self.deleted = set()

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_callback_invalid_data(monkeypatch):
    cb = FakeCallbackQuery(data="bad")
    monkeypatch.setattr(callbacks, "parse_callback", lambda _d: None)

    await callbacks.handle_task_callback(cb)

    assert cb.answers and "неверные данные" in cb.answers[0][0]


@pytest.mark.asyncio
async def test_callback_permission_denied(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:take")
    monkeypatch.setattr(callbacks, "parse_callback", lambda _d: (1, "take"))
    monkeypatch.setattr(callbacks, "is_allowed", lambda _a, _u: False)

    await callbacks.handle_task_callback(cb)

    assert cb.answers and cb.answers[0][0] == callbacks.denied_message("take")


@pytest.mark.asyncio
async def test_callback_task_not_found(monkeypatch):
    cb_message = __import__("tests.fakes", fromlist=["FakeMessage"]).FakeMessage(text="x")
    cb = FakeCallbackQuery(data="task:1:open", message=cb_message)

    session = _Session()
    monkeypatch.setattr(callbacks, "parse_callback", lambda _d: (1, "open"))
    monkeypatch.setattr(callbacks, "is_allowed", lambda _a, _u: True)
    monkeypatch.setattr(callbacks, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(callbacks, "resolve_known_roles", lambda *_a, **_k: __import__("asyncio").sleep(0))

    async def _missing_task(*_args, **_kwargs):
        return None

    monkeypatch.setattr(callbacks.task_repo, "get_task_by_id", _missing_task)

    await callbacks.handle_task_callback(cb)

    assert cb.answers and "не найдена" in cb.answers[0][0]


@pytest.mark.asyncio
async def test_callback_dispatches_handler_and_commits(monkeypatch):
    from tests.fakes import FakeMessage

    msg = FakeMessage(text="x", chat_id=-100, topic_id=777)
    cb = FakeCallbackQuery(data="task:5:open", message=msg, from_user=make_user(7, "actor"))

    session = _Session(pending=False)
    task = FakeTask(id=5, chat_id=-100, topic_id=777)
    called = {"value": False}

    async def _resolve(*_args, **_kwargs):
        return False

    async def _get_task(*_args, **_kwargs):
        return task

    async def _handler(callback, task_obj, *_args):
        called["value"] = True
        assert callback is cb
        assert task_obj.id == 5

    monkeypatch.setattr(callbacks, "parse_callback", lambda _d: (5, "open"))
    monkeypatch.setattr(callbacks, "is_allowed", lambda _a, _u: True)
    monkeypatch.setattr(callbacks, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(callbacks, "resolve_known_roles", _resolve)
    monkeypatch.setattr(callbacks.task_repo, "get_task_by_id", _get_task)
    monkeypatch.setattr(callbacks, "ACTION_HANDLERS", {"open": _handler})

    await callbacks.handle_task_callback(cb)

    assert called["value"] is True
    assert session.commits == 0


@pytest.mark.asyncio
async def test_callback_dispatches_handler_and_commits_when_pending(monkeypatch):
    from tests.fakes import FakeMessage

    msg = FakeMessage(text="x", chat_id=-100, topic_id=777)
    cb = FakeCallbackQuery(data="task:5:open", message=msg, from_user=make_user(7, "actor"))

    session = _Session(pending=True)
    task = FakeTask(id=5, chat_id=-100, topic_id=777)

    async def _resolve(*_args, **_kwargs):
        return False

    async def _get_task(*_args, **_kwargs):
        return task

    async def _handler(*_args, **_kwargs):
        return None

    monkeypatch.setattr(callbacks, "parse_callback", lambda _d: (5, "open"))
    monkeypatch.setattr(callbacks, "is_allowed", lambda _a, _u: True)
    monkeypatch.setattr(callbacks, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(callbacks, "resolve_known_roles", _resolve)
    monkeypatch.setattr(callbacks.task_repo, "get_task_by_id", _get_task)
    monkeypatch.setattr(callbacks, "ACTION_HANDLERS", {"open": _handler})

    await callbacks.handle_task_callback(cb)

    assert session.commits == 1
