import pytest

from core.config import runtime
from handlers.commands import settings
from tests.fakes import FakeCallbackQuery, FakeMessage, FakeSessionFactory, make_user


class _Session:
    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_cmd_settings_denies_non_admin(monkeypatch):
    msg = FakeMessage(text="/settings", from_user=make_user(1, "user"))
    monkeypatch.setattr(settings, "is_admin", lambda _u: False)

    await settings.cmd_settings(msg)

    assert msg.replies and "только администраторам" in msg.replies[0][0].lower()


@pytest.mark.asyncio
async def test_cmd_settings_snapshot(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="/settings", from_user=make_user(1, "admin"))

    monkeypatch.setattr(settings, "is_admin", lambda _u: True)
    monkeypatch.setattr(settings, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(settings, "resolve_admin_identity", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))

    await settings.cmd_settings(msg)

    assert msg.replies and "Текущие runtime-настройки" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_settings_invalid_confidence(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="/settings confidence 2", from_user=make_user(1, "admin"))

    monkeypatch.setattr(settings, "is_admin", lambda _u: True)
    monkeypatch.setattr(settings, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(settings, "resolve_admin_identity", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))

    await settings.cmd_settings(msg)

    assert msg.replies and "диапазоне 0..1" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cb_settings_show_denied_for_wrong_context(monkeypatch):
    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    cb = FakeCallbackQuery(
        data="settings:show",
        from_user=make_user(2, "user"),
        message=FakeMessage(text="x", chat_id=-100, topic_id=777),
    )

    monkeypatch.setattr(settings, "is_admin", lambda _u: False)

    await settings.cb_settings_show(cb)

    assert cb.answers and "только администраторам" in (cb.answers[0][0] or "").lower()
