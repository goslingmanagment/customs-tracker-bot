from types import SimpleNamespace

import pytest

from core.config import roles
from services import role_service


@pytest.mark.asyncio
async def test_load_role_cache_populates_globals(monkeypatch):
    rows = [
        SimpleNamespace(role="admin", user_id=1, username="admin1"),
        SimpleNamespace(role="model", user_id=2, username="model1"),
        SimpleNamespace(role="teamlead", user_id=3, username="lead1"),
        SimpleNamespace(role="unknown", user_id=4, username="nope"),
    ]

    async def _load_all(_session):
        return rows

    monkeypatch.setattr(role_service.role_repo, "load_all_role_memberships", _load_all)

    cache = await role_service.load_role_cache(object())

    assert cache["admin"]["ids"] == [1]
    assert cache["model"]["usernames"] == ["model1"]
    assert roles.teamlead_ids == [3]


@pytest.mark.asyncio
async def test_resolve_known_roles_commits_only_when_changed(monkeypatch):
    class _Session:
        def __init__(self):
            self.commits = 0

        async def commit(self):
            self.commits += 1

    session = _Session()

    calls: list[str] = []

    async def _resolve(user, role, _session):
        calls.append(role)
        return role == "model"

    async def _load(_session):
        calls.append("load")
        return {}

    monkeypatch.setattr(role_service, "_resolve_role_identity_in_session", _resolve)
    monkeypatch.setattr(role_service, "load_role_cache", _load)

    changed = await role_service.resolve_known_roles(
        SimpleNamespace(id=1, username="u", full_name="User"),
        session,
    )

    assert changed is True
    assert session.commits == 1
    assert calls[-1] == "load"


@pytest.mark.asyncio
async def test_resolve_admin_identity_false_without_user():
    changed = await role_service.resolve_admin_identity(None, object())
    assert changed is False
