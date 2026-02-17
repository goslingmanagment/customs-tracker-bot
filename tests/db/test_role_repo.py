import pytest
from sqlalchemy import select

from db.models import RoleMembership
from db.repo import role_repo


@pytest.mark.asyncio
async def test_upsert_role_member_requires_identifier(db_session):
    with pytest.raises(ValueError):
        await role_repo.upsert_role_member(db_session, "admin")


@pytest.mark.asyncio
async def test_upsert_and_remove_by_username_and_id(db_session):
    row, created = await role_repo.upsert_role_member(db_session, "model", username="@ModelA")
    assert created is True
    assert row.username == "modela"

    row2, created2 = await role_repo.upsert_role_member(db_session, "model", user_id=42)
    assert created2 is True
    assert row2.user_id == 42

    assert await role_repo.remove_role_member(db_session, "model", username="ModelA") is True
    assert await role_repo.remove_role_member(db_session, "model", user_id=42) is True
    assert await role_repo.remove_role_member(db_session, "model", user_id=999) is False


@pytest.mark.asyncio
async def test_upsert_merges_duplicate_partial_entries(db_session):
    by_id, _ = await role_repo.upsert_role_member(db_session, "admin", user_id=100)
    by_username, _ = await role_repo.upsert_role_member(db_session, "admin", username="boss")

    merged, created = await role_repo.upsert_role_member(
        db_session,
        "admin",
        user_id=100,
        username="boss",
    )

    assert created is False
    assert merged.id == by_id.id
    assert merged.user_id == 100
    assert merged.username == "boss"

    rows = (
        await db_session.execute(select(RoleMembership).where(RoleMembership.role == "admin"))
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_and_load_all_memberships(db_session):
    await role_repo.upsert_role_member(db_session, "admin", user_id=1)
    await role_repo.upsert_role_member(db_session, "model", username="m1")

    admins = await role_repo.list_role_members(db_session, "admin")
    assert len(admins) == 1

    all_rows = await role_repo.load_all_role_memberships(db_session)
    assert {row.role for row in all_rows} == {"admin", "model"}
