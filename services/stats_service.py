"""Monthly analytics."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.log_utils import today_local
from db.models import Task


async def get_monthly_stats(session: AsyncSession, year: int, month: int) -> dict:
    month_prefix = f"{year}-{month:02d}"
    result = await session.execute(
        select(Task).where(Task.created_at.startswith(month_prefix))
    )
    tasks = list(result.scalars().all())

    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "delivered")
    in_progress = sum(
        1 for t in tasks
        if t.status in ("draft", "awaiting_confirmation", "processing")
    )
    cancelled = sum(1 for t in tasks if t.status == "cancelled")
    finished = sum(1 for t in tasks if t.status == "finished")

    total_amount = sum(t.amount_total or 0 for t in tasks)
    avg_amount = total_amount / total if total > 0 else 0

    overdue = 0
    today = today_local()
    for t in tasks:
        if t.deadline and t.status not in ("delivered", "cancelled"):
            if t.deadline < today:
                overdue += 1

    platforms: dict[str, dict] = {}
    for t in tasks:
        p = t.platform or "unknown"
        if p not in platforms:
            platforms[p] = {"count": 0, "amount": 0.0}
        platforms[p]["count"] += 1
        platforms[p]["amount"] += t.amount_total or 0

    return {
        "total": total,
        "completed": completed,
        "in_progress": in_progress,
        "finished": finished,
        "cancelled": cancelled,
        "overdue": overdue,
        "total_amount": total_amount,
        "avg_amount": avg_amount,
        "platforms": platforms,
    }
