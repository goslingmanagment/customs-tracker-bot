"""Role membership CRUD. Repos never commit — callers commit."""

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.text_utils import normalize_username
from db.models import RoleMembership


async def list_role_members(session: AsyncSession, role: str) -> list[RoleMembership]:
    normalized_role = role.strip().lower()
    result = await session.execute(
        select(RoleMembership)
        .where(RoleMembership.role == normalized_role)
        .order_by(RoleMembership.created_at.asc(), RoleMembership.id.asc())
    )
    return list(result.scalars().all())


async def upsert_role_member(
    session: AsyncSession,
    role: str,
    *,
    user_id: int | None = None,
    username: str | None = None,
    created_by_id: int | None = None,
    created_by_name: str | None = None,
) -> tuple[RoleMembership, bool]:
    """Insert/update role membership. Merges duplicate partial entries."""
    normalized_role = role.strip().lower()
    normalized_username = normalize_username(username)

    if user_id is None and not normalized_username:
        raise ValueError("user_id or username is required")

    by_id: RoleMembership | None = None
    by_username: RoleMembership | None = None

    if user_id is not None:
        by_id_result = await session.execute(
            select(RoleMembership).where(
                RoleMembership.role == normalized_role,
                RoleMembership.user_id == user_id,
            )
        )
        by_id = by_id_result.scalar_one_or_none()

    if normalized_username:
        by_username_result = await session.execute(
            select(RoleMembership).where(
                RoleMembership.role == normalized_role,
                RoleMembership.username == normalized_username,
            )
        )
        by_username = by_username_result.scalar_one_or_none()

    existing = by_id or by_username
    created = False

    if by_id and by_username and by_id.id != by_username.id:
        primary = by_id
        secondary = by_username
        secondary_user_id = secondary.user_id
        secondary_username = secondary.username

        # Avoid transient unique conflicts during flush by removing the
        # duplicate row first, then copying missing identity fields.
        await session.delete(secondary)
        await session.flush()

        if primary.user_id is None:
            primary.user_id = secondary_user_id
        if not primary.username and secondary_username:
            primary.username = secondary_username
        primary.updated_at = datetime.now(timezone.utc).isoformat()
        existing = primary
    elif existing:
        if user_id is not None and existing.user_id != user_id:
            existing.user_id = user_id
        if normalized_username and existing.username != normalized_username:
            existing.username = normalized_username
        existing.updated_at = datetime.now(timezone.utc).isoformat()
    else:
        existing = RoleMembership(
            role=normalized_role,
            user_id=user_id,
            username=normalized_username,
            created_by_id=created_by_id,
            created_by_name=created_by_name,
        )
        session.add(existing)
        created = True

    await session.flush()
    return existing, created


async def remove_role_member(
    session: AsyncSession,
    role: str,
    *,
    user_id: int | None = None,
    username: str | None = None,
) -> bool:
    normalized_role = role.strip().lower()
    normalized_username = normalize_username(username)
    if user_id is None and not normalized_username:
        raise ValueError("user_id or username is required")

    membership_query = select(RoleMembership).where(RoleMembership.role == normalized_role)
    if user_id is not None and normalized_username:
        membership_query = membership_query.where(
            or_(
                RoleMembership.user_id == user_id,
                RoleMembership.username == normalized_username,
            )
        )
    elif user_id is not None:
        membership_query = membership_query.where(RoleMembership.user_id == user_id)
    else:
        membership_query = membership_query.where(
            RoleMembership.username == normalized_username
        )

    result = await session.execute(membership_query)
    rows = list(result.scalars().all())
    if not rows:
        return False

    for row in rows:
        await session.delete(row)

    await session.flush()
    return True


async def load_all_role_memberships(session: AsyncSession) -> list[RoleMembership]:
    result = await session.execute(
        select(RoleMembership).order_by(RoleMembership.role.asc(), RoleMembership.id.asc())
    )
    return list(result.scalars().all())
