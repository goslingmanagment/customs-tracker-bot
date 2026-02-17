import pytest

from core.config import runtime
from db.models import RoleMembership
from handlers.commands import roles
from tests.fakes import FakeMessage, FakeSessionFactory, make_user


class _Session:
    async def commit(self):
        return None


def test_format_member_line_variants():
    assert roles._format_member_line(RoleMembership(role="admin", user_id=1, username="boss")) == "@boss (ID: <code>1</code>)"
    assert roles._format_member_line(RoleMembership(role="admin", user_id=None, username="boss")) == "@boss"
    assert roles._format_member_line(RoleMembership(role="admin", user_id=1, username=None)) == "ID: <code>1</code>"


@pytest.mark.asyncio
async def test_cmd_roles_denies_non_admin():
    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    msg = FakeMessage(text="/roles", chat_id=-100, topic_id=777, from_user=make_user(2, "user"))

    await roles.cmd_roles(msg)

    assert msg.replies and "Только администраторы" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_admin_without_args_shows_usage(monkeypatch):
    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    session = _Session()
    msg = FakeMessage(text="/admin", chat_id=-100, topic_id=777, from_user=make_user(1, "admin"))

    monkeypatch.setattr(roles, "is_admin", lambda _u: True)
    monkeypatch.setattr(roles, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(roles, "resolve_admin_identity", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))

    await roles.cmd_admin(msg)

    assert msg.replies and "Управление админами" in msg.replies[0][0]
