from types import SimpleNamespace

import pytest

from core.config import runtime
from handlers.commands import settings


class _FakeSession:
    async def commit(self):
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


class _FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.from_user = SimpleNamespace(id=100, username="admin", full_name="Admin")
        self.replies: list[str] = []

    async def reply(self, text: str, **_kwargs):
        self.replies.append(text)


@pytest.mark.asyncio
async def test_settings_timezone_is_locked(monkeypatch):
    session = _FakeSession()
    message = _FakeMessage("/settings timezone Europe/Kyiv")
    upsert_called = {"value": False}

    monkeypatch.setattr(settings, "is_admin", lambda _user: True)
    monkeypatch.setattr(settings, "async_session", _FakeSessionFactory(session))

    async def _resolve_admin_identity(_user, _session):
        return False

    async def _upsert(*_args, **_kwargs):
        upsert_called["value"] = True

    monkeypatch.setattr(settings, "resolve_admin_identity", _resolve_admin_identity)
    monkeypatch.setattr(settings.settings_repo, "upsert_app_settings", _upsert)

    await settings.cmd_settings(message)

    assert upsert_called["value"] is False
    assert len(message.replies) == 1
    assert "фиксирован" in message.replies[0]


@pytest.mark.asyncio
async def test_settings_updates_confidence(monkeypatch):
    session = _FakeSession()
    message = _FakeMessage("/settings confidence 0.8")
    captured_kwargs: dict[str, object] = {}

    runtime.ai_confidence_threshold = 0.7

    monkeypatch.setattr(settings, "is_admin", lambda _user: True)
    monkeypatch.setattr(settings, "async_session", _FakeSessionFactory(session))

    async def _resolve_admin_identity(_user, _session):
        return False

    async def _upsert(_session, **kwargs):
        captured_kwargs.update(kwargs)

    async def _load_runtime_settings(_session):
        runtime.ai_confidence_threshold = 0.8
        return {"ai_confidence_threshold": 0.8}

    monkeypatch.setattr(settings, "resolve_admin_identity", _resolve_admin_identity)
    monkeypatch.setattr(settings.settings_repo, "upsert_app_settings", _upsert)
    monkeypatch.setattr(settings, "load_runtime_settings", _load_runtime_settings)

    await settings.cmd_settings(message)

    assert captured_kwargs == {"ai_confidence_threshold": 0.8}
    assert len(message.replies) == 1
    assert "обновлена" in message.replies[0]
