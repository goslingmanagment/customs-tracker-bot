"""AppSettings CRUD. Repos never commit — callers commit."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AppSettings


async def ensure_app_settings_row(session: AsyncSession) -> AppSettings:
    result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row:
        return row

    row = AppSettings(id=1)
    session.add(row)
    await session.flush()
    return row


async def get_app_settings(session: AsyncSession) -> AppSettings:
    result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row:
        return row
    return await ensure_app_settings_row(session)


async def upsert_app_settings(
    session: AsyncSession,
    *,
    customs_chat_id: int | None = None,
    customs_topic_id: int | None = None,
    ai_model: str | None = None,
    ai_confidence_threshold: float | None = None,
    reminder_hours_before: int | None = None,
    overdue_reminder_cooldown_hours: int | None = None,
    high_urgency_cooldown_hours: int | None = None,
    finished_reminder_hours: int | None = None,
    timezone_name: str | None = None,
) -> AppSettings:
    row = await ensure_app_settings_row(session)

    if customs_chat_id is not None:
        row.customs_chat_id = int(customs_chat_id)
    if customs_topic_id is not None:
        row.customs_topic_id = int(customs_topic_id)
    if ai_model is not None:
        row.ai_model = str(ai_model).strip()
    if ai_confidence_threshold is not None:
        row.ai_confidence_threshold = float(ai_confidence_threshold)
    if reminder_hours_before is not None:
        row.reminder_hours_before = int(reminder_hours_before)
    if overdue_reminder_cooldown_hours is not None:
        row.overdue_reminder_cooldown_hours = int(overdue_reminder_cooldown_hours)
    if high_urgency_cooldown_hours is not None:
        row.high_urgency_cooldown_hours = int(high_urgency_cooldown_hours)
    if finished_reminder_hours is not None:
        row.finished_reminder_hours = int(finished_reminder_hours)
    if timezone_name is not None:
        row.timezone = str(timezone_name).strip()

    row.updated_at = datetime.now(timezone.utc).isoformat()
    await session.flush()
    return row
