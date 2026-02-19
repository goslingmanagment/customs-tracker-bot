"""Morning summary for operators — single daily notification."""

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import runtime
from core.log_utils import today_local
from core.text_utils import esc
from db.repo import task_repo
from ui.formatters import format_amount, format_days_overdue

logger = structlog.get_logger()

_SECTION_LIMIT = 10


async def send_morning_digest(bot: Bot, session: AsyncSession) -> None:
    today = today_local()
    active_tasks = await task_repo.get_active_tasks(session)
    if not active_tasks:
        return

    overdue_tasks = await task_repo.get_overdue_tasks(session, today=today)
    due_soon = await task_repo.get_tasks_due_soon(session, days=1, today=today)
    due_today = [t for t in due_soon if t.deadline == today]

    reminder_hours = max(1, runtime.finished_reminder_hours)
    finished_pending = await task_repo.get_finished_tasks_older_than_hours(
        session, reminder_hours
    )

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
            f"Дедлайн сегодня: <b>{len(due_today)}</b>"
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

    if overdue_tasks:
        lines.append("")
        lines.append(f"🚨 <b>Просроченные ({len(overdue_tasks)}):</b>")
        for t in overdue_tasks[:_SECTION_LIMIT]:
            days = format_days_overdue(t.deadline)
            lines.append(
                f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
                f"{esc((t.description or '—')[:40])} | {days}"
            )
        if len(overdue_tasks) > _SECTION_LIMIT:
            lines.append(f"  ... и ещё {len(overdue_tasks) - _SECTION_LIMIT}")

    if due_today:
        lines.append("")
        lines.append(f"⏰ <b>Дедлайн сегодня ({len(due_today)}):</b>")
        for t in due_today[:_SECTION_LIMIT]:
            lines.append(
                f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
                f"{esc((t.description or '—')[:40])}"
            )
        if len(due_today) > _SECTION_LIMIT:
            lines.append(f"  ... и ещё {len(due_today) - _SECTION_LIMIT}")

    if finished_pending:
        lines.append("")
        lines.append(f"⏳ <b>Отснято, но не доставлено ({len(finished_pending)}):</b>")
        for t in finished_pending[:_SECTION_LIMIT]:
            lines.append(
                f"  #{t.id:03d} | {esc((t.description or '—')[:40])}"
            )
        if len(finished_pending) > _SECTION_LIMIT:
            lines.append(f"  ... и ещё {len(finished_pending) - _SECTION_LIMIT}")

    try:
        await bot.send_message(
            chat_id=runtime.customs_chat_id,
            message_thread_id=runtime.customs_topic_id,
            text="\n".join(lines),
        )
    except Exception as exc:
        logger.error("morning_digest_send_error", error=str(exc))
