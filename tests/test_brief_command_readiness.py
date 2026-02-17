from types import SimpleNamespace

import pytest

from handlers.commands import brief


class _FakeSession:
    async def commit(self):
        return None

    async def rollback(self):
        return None


class _FakeSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return _FakeSessionContext(self._session)


class _FakeLogger:
    def __init__(self):
        self.warning_calls: list[tuple[str, dict]] = []

    def warning(self, event: str, **kwargs):
        self.warning_calls.append((event, kwargs))

    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class _FakeMessage:
    def __init__(self):
        self.message_id = 300
        self.chat = SimpleNamespace(id=-1001)
        self.message_thread_id = 777
        self.from_user = SimpleNamespace(id=1000, username="admin", full_name="Admin")
        self.text = "/add"
        self.reply_to_message = SimpleNamespace(
            message_id=301,
            chat=SimpleNamespace(id=-1001),
            message_thread_id=777,
            text="📦 Test brief",
            caption=None,
            photo=[],
            from_user=SimpleNamespace(id=2000, username="sender"),
            reply=None,
        )
        self.replies: list[tuple[str, dict]] = []

        async def _reply(text: str, **kwargs):
            self.replies.append((text, kwargs))
            return SimpleNamespace(message_id=999)

        self.reply_to_message.reply = _reply

    async def reply(self, text: str, **kwargs):
        self.replies.append((text, kwargs))


@pytest.mark.asyncio
async def test_add_exits_before_ai_when_env_blocked(monkeypatch):
    message = _FakeMessage()
    session = _FakeSession()

    monkeypatch.setattr(brief, "can_add_brief", lambda _user: True)
    monkeypatch.setattr(brief, "async_session", _FakeSessionFactory(session))

    async def _resolve_known_roles(_user, _session):
        return False

    async def _get_task_by_message(_session, _chat_id, _message_id):
        return None

    monkeypatch.setattr(brief, "resolve_known_roles", _resolve_known_roles)
    monkeypatch.setattr(brief.task_repo, "get_task_by_message", _get_task_by_message)

    monkeypatch.setattr(
        brief,
        "evaluate_brief_env_readiness",
        lambda: SimpleNamespace(ready=False, blockers=["anthropic_api_key_missing"], warnings=[]),
    )
    monkeypatch.setattr(
        brief,
        "summarize_readiness_for_log",
        lambda readiness: {
            "ready": readiness.ready,
            "blockers": readiness.blockers,
            "warnings": readiness.warnings,
        },
    )

    classify_called = {"value": False}
    create_called = {"value": False}

    async def _classify_message(_text, _has_photo=False):
        classify_called["value"] = True
        return None

    async def _create_task(_session, **_kwargs):
        create_called["value"] = True
        return None, False

    monkeypatch.setattr(brief, "classify_message", _classify_message)
    monkeypatch.setattr(brief.task_repo, "create_task", _create_task)

    fake_logger = _FakeLogger()
    monkeypatch.setattr(brief, "logger", fake_logger)

    await brief.cmd_add(message)

    assert classify_called["value"] is False
    assert create_called["value"] is False
    assert len(message.replies) == 1
    assert "/health" in message.replies[0][0]
    assert fake_logger.warning_calls
    assert fake_logger.warning_calls[0][0] == "manual_add_blocked_by_env"
