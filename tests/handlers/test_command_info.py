import pytest

from core.config import roles
from handlers.commands import info
from tests.fakes import FakeMessage, make_user


@pytest.mark.asyncio
async def test_cmd_help_admin_contains_admin_section(monkeypatch):
    msg = FakeMessage(text="/help", from_user=make_user(1, "admin"))

    monkeypatch.setattr(info, "is_admin", lambda _u: True)
    monkeypatch.setattr(info, "is_teamlead", lambda _u: False)
    monkeypatch.setattr(info, "is_model", lambda _u: False)

    await info.cmd_help(msg)

    assert msg.replies and "Админ-команды" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_id_outputs_chat_and_topic():
    msg = FakeMessage(text="/id", chat_id=-100, topic_id=777)
    await info.cmd_id(msg)

    assert msg.replies and "Chat ID" in msg.replies[0][0]
    assert "Topic ID" in msg.replies[0][0]


@pytest.mark.asyncio
async def test_cmd_health_denies_non_admin_when_admins_configured():
    roles.admin_ids = [100]
    roles.admin_usernames = []

    msg = FakeMessage(text="/health", from_user=make_user(1, "user"))

    await info.cmd_health(msg)

    assert msg.replies and "Доступно только администраторам" in msg.replies[0][0]
