"""Morning summary for operators."""

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import runtime
from core.log_utils import today_local
from db.repo import task_repo
from ui.formatters import format_amount

logger = structlog.get_logger()


async def send_morning_digest(bot: Bot, session: AsyncSession) -> None:
    today = today_local()
    active_tasks = await task_repo.get_active_tasks(session)
    if not active_tasks:
        return

    overdue_tasks = await task_repo.get_overdue_tasks(session, today=today)
    due_soon = await task_repo.get_tasks_due_soon(session, days=1, today=today)
    due_today_count = sum(1 for task in due_soon if task.deadline == today)

    status_counts = {
        "draft": 0,
        "awaiting_confirmation": 0,
        "processing": 0,
        "finished": 0,
    }
    for task in active_tasks:
        if task.status in status_counts:
            status_counts[task.status] += 1

    total_amount = sum(task.amount_total or 0 for task in active_tasks)
    lines = [
        "🌅 <b>Утренний дайджест</b>",
        (
            f"Активных: <b>{len(active_tasks)}</b> | "
            f"Просрочено: <b>{len(overdue_tasks)}</b> | "
            f"Дедлайн сегодня: <b>{due_today_count}</b>"
        ),
        (
            "Статусы: "
            f"черновик <b>{status_counts['draft']}</b>, "
            f"ожидает модель <b>{status_counts['awaiting_confirmation']}</b>, "
            f"в работе <b>{status_counts['processing']}</b>, "
            f"отснято <b>{status_counts['finished']}</b>"
        ),
        f"Сумма активных: <b>{format_amount(total_amount)}</b>",
    ]

    try:
        await bot.send_message(
            chat_id=runtime.customs_chat_id,
            message_thread_id=runtime.customs_topic_id,
            text="\n".join(lines),
        )
    except Exception as exc:
        logger.error("morning_digest_send_error", error=str(exc))
