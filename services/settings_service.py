"""Load/save runtime settings, syncing DB to core.config.runtime."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import runtime
from db.repo import settings_repo

logger = structlog.get_logger()

RUNTIME_TIMEZONE = "Europe/Moscow"


async def load_runtime_settings(session: AsyncSession) -> dict[str, int | float | str]:
    """Load settings from DB into core.config.runtime. Returns dict for logging."""
    row = await settings_repo.get_app_settings(session)
    runtime.customs_chat_id = int(row.customs_chat_id or 0)
    runtime.customs_topic_id = int(row.customs_topic_id or 0)
    runtime.ai_model = str(row.ai_model or "")
    runtime.ai_confidence_threshold = float(row.ai_confidence_threshold)
    runtime.reminder_hours_before = int(row.reminder_hours_before)
    runtime.overdue_reminder_cooldown_hours = int(row.overdue_reminder_cooldown_hours)
    runtime.high_urgency_cooldown_hours = int(row.high_urgency_cooldown_hours)
    runtime.finished_reminder_hours = int(row.finished_reminder_hours)

    db_timezone = str(row.timezone or "").strip()
    if db_timezone and db_timezone != RUNTIME_TIMEZONE:
        logger.warning(
            "runtime_timezone_overridden",
            db_timezone=db_timezone,
            effective_timezone=RUNTIME_TIMEZONE,
        )
    runtime.timezone = RUNTIME_TIMEZONE

    return {
        "customs_chat_id": runtime.customs_chat_id,
        "customs_topic_id": runtime.customs_topic_id,
        "ai_model": runtime.ai_model,
        "ai_confidence_threshold": runtime.ai_confidence_threshold,
        "reminder_hours_before": runtime.reminder_hours_before,
        "overdue_reminder_cooldown_hours": runtime.overdue_reminder_cooldown_hours,
        "high_urgency_cooldown_hours": runtime.high_urgency_cooldown_hours,
        "finished_reminder_hours": runtime.finished_reminder_hours,
        "timezone": runtime.timezone,
    }
