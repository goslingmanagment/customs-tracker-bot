"""Overdue task alerts."""

from datetime import datetime, timezone

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import runtime
from core.log_utils import today_local
from core.text_utils import esc
from db.repo import task_repo
from ui.formatters import format_amount, format_days_overdue

logger = structlog.get_logger()


def _should_remind(task, now: datetime) -> bool:
    if not task.last_reminder_at:
        return True
    try:
        last = datetime.fromisoformat(task.last_reminder_at)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    cooldown_hours = (
        runtime.high_urgency_cooldown_hours
        if task.priority == "high"
        else runtime.overdue_reminder_cooldown_hours
    )
    return (now - last).total_seconds() > cooldown_hours * 3600


async def check_overdue_and_remind(bot: Bot, session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    today = today_local()

    overdue = await task_repo.get_overdue_tasks(session, today=today)
    tasks_to_remind = [t for t in overdue if _should_remind(t, now)]

    if not tasks_to_remind:
        return

    lines = [f"🚨 <b>Просроченные кастомы: {len(tasks_to_remind)}</b>\n"]
    for t in tasks_to_remind:
        days = format_days_overdue(t.deadline)
        lines.append(
            f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
            f"{esc((t.description or '—')[:40])} | {days}"
        )

    try:
        await bot.send_message(
            chat_id=runtime.customs_chat_id,
            message_thread_id=runtime.customs_topic_id,
            text="\n".join(lines),
        )
    except Exception as e:
        logger.error("reminder_send_error", error=str(e))
        return

    for t in tasks_to_remind:
        t.last_reminder_at = now.isoformat()
    await session.commit()
