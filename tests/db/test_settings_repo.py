import pytest

from db.repo import settings_repo


@pytest.mark.asyncio
async def test_ensure_get_settings_row(db_session):
    row = await settings_repo.ensure_app_settings_row(db_session)
    assert row.id == 1

    got = await settings_repo.get_app_settings(db_session)
    assert got.id == 1


@pytest.mark.asyncio
async def test_upsert_updates_selected_fields(db_session):
    row = await settings_repo.upsert_app_settings(
        db_session,
        customs_chat_id=-100,
        customs_topic_id=777,
        ai_model="claude-x",
        ai_confidence_threshold=0.8,
        reminder_hours_before=12,
        overdue_reminder_cooldown_hours=3,
        high_urgency_cooldown_hours=1,
        finished_reminder_hours=10,
        timezone_name="UTC",
    )

    assert row.customs_chat_id == -100
    assert row.customs_topic_id == 777
    assert row.ai_model == "claude-x"
    assert row.ai_confidence_threshold == 0.8
    assert row.reminder_hours_before == 12
    assert row.overdue_reminder_cooldown_hours == 3
    assert row.high_urgency_cooldown_hours == 1
    assert row.finished_reminder_hours == 10
    assert row.timezone == "UTC"
