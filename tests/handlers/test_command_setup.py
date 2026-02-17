import pytest

from handlers.commands import setup
from tests.fakes import FakeMessage, FakeSessionFactory, make_user


class _Session:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_cmd_setup_requires_topic():
    msg = FakeMessage(text="/setup", topic_id=None)

    await setup.cmd_setup(msg)

    assert msg.replies and "внутри топика" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_setup_bootstraps_first_admin(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="/setup", chat_id=-100, topic_id=777, from_user=make_user(1, "admin"))

    async def _list_members(*_args, **_kwargs):
        return []

    async def _upsert(*_args, **_kwargs):
        return None

    async def _upsert_settings(*_args, **_kwargs):
        return None

    monkeypatch.setattr(setup, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(setup.role_repo, "list_role_members", _list_members)
    monkeypatch.setattr(setup.role_repo, "upsert_role_member", _upsert)
    monkeypatch.setattr(setup.settings_repo, "upsert_app_settings", _upsert_settings)
    monkeypatch.setattr(setup, "load_runtime_settings", lambda *_a, **_k: __import__("asyncio").sleep(0))
    monkeypatch.setattr(setup, "load_role_cache", lambda *_a, **_k: __import__("asyncio").sleep(0))

    await setup.cmd_setup(msg)

    assert session.commits == 1
    assert msg.replies and "Бот привязан" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_setup_denies_non_admin_after_bootstrap(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="/setup", chat_id=-100, topic_id=777, from_user=make_user(2, "user"))

    monkeypatch.setattr(setup, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(setup.role_repo, "list_role_members", lambda *_a, **_k: __import__("asyncio").sleep(0, result=[object()]))
    monkeypatch.setattr(setup, "is_admin", lambda _u: False)

    await setup.cmd_setup(msg)

    assert msg.replies and "Только администраторы" in msg.replies[0][0]
