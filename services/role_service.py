"""Role business logic — loading cache, resolving identities."""

import structlog
from aiogram.types import User
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import roles
from core.permissions import get_role_cache
from core.text_utils import normalize_username
from db.repo import role_repo

logger = structlog.get_logger()


async def load_role_cache(session: AsyncSession) -> dict[str, dict[str, list]]:
    """Load all roles from DB into core.config.roles."""
    rows = await role_repo.load_all_role_memberships(session)

    cache: dict[str, dict[str, list]] = {
        "admin": {"ids": [], "usernames": []},
        "model": {"ids": [], "usernames": []},
        "teamlead": {"ids": [], "usernames": []},
    }

    for row in rows:
        if row.role not in cache:
            continue
        if row.user_id is not None and row.user_id not in cache[row.role]["ids"]:
            cache[row.role]["ids"].append(int(row.user_id))
        if row.username and row.username not in cache[row.role]["usernames"]:
            cache[row.role]["usernames"].append(row.username)

    roles.admin_ids = cache["admin"]["ids"]
    roles.admin_usernames = cache["admin"]["usernames"]
    roles.model_ids = cache["model"]["ids"]
    roles.model_usernames = cache["model"]["usernames"]
    roles.teamlead_ids = cache["teamlead"]["ids"]
    roles.teamlead_usernames = cache["teamlead"]["usernames"]

    return cache


async def _resolve_role_identity_in_session(
    user: User, role: str, session: AsyncSession
) -> bool:
    role_ids, role_usernames = get_role_cache(role)
    normalized_username = normalize_username(user.username)
    if user.id in role_ids or not normalized_username:
        return False

    if normalized_username not in {
        normalize_username(item) for item in role_usernames if item
    }:
        return False

    await role_repo.upsert_role_member(
        session,
        role,
        user_id=user.id,
        username=normalized_username,
        created_by_id=user.id,
        created_by_name=user.username or user.full_name,
    )
    logger.info(
        "role_identity_resolved",
        role=role,
        username=normalized_username,
        user_id=user.id,
    )
    return True


async def resolve_known_roles(user: User | None, session: AsyncSession) -> bool:
    """If user is known by username but not ID, update DB and refresh cache."""
    if not user:
        return False
    changed_admin = await _resolve_role_identity_in_session(user, "admin", session)
    changed_model = await _resolve_role_identity_in_session(user, "model", session)
    changed_teamlead = await _resolve_role_identity_in_session(user, "teamlead", session)
    changed = changed_admin or changed_model or changed_teamlead
    if changed:
        await session.commit()
        await load_role_cache(session)
    return changed


async def resolve_admin_identity(user: User | None, session: AsyncSession) -> bool:
    if not user:
        return False
    changed = await _resolve_role_identity_in_session(user, "admin", session)
    if changed:
        await session.commit()
        await load_role_cache(session)
    return changed
