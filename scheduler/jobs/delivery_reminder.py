"""Finished-not-delivered task alerts."""

from datetime import datetime, timezone

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import runtime
from db.repo import task_repo

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
    cooldown_hours = runtime.overdue_reminder_cooldown_hours
    return (now - last).total_seconds() > cooldown_hours * 3600


async def check_finished_pending_delivery(bot: Bot, session: AsyncSession) -> None:
    reminder_hours = max(1, runtime.finished_reminder_hours)
    now = datetime.now(timezone.utc)

    tasks = await task_repo.get_finished_tasks_older_than_hours(session, reminder_hours)
    tasks_to_remind = [t for t in tasks if _should_remind(t, now)]
    if not tasks_to_remind:
        return

    lines = [f"⏳ <b>Отснято, но не доставлено: {len(tasks_to_remind)}</b>\n"]
    for t in tasks_to_remind:
        lines.append(
            f"  ⏳ Кастом #{t.id:03d} отснят более {reminder_hours}ч назад, но не доставлен"
        )

    try:
        await bot.send_message(
            chat_id=runtime.customs_chat_id,
            message_thread_id=runtime.customs_topic_id,
            text="\n".join(lines),
        )
    except Exception as exc:
        logger.error("finished_delivery_reminder_send_error", error=str(exc))
        return

    for t in tasks_to_remind:
        t.last_reminder_at = now.isoformat()
    await session.commit()
