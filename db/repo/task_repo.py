"""Task CRUD and queries. Repos never commit — callers commit."""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.constants import VALID_TRANSITIONS
from core.exceptions import InvalidTransitionError
from core.log_utils import today_local
from db.models import StatusLog, Task

logger = structlog.get_logger()


def _apply_status_timestamps(task: Task, new_status: str, now_iso: str) -> None:
    if new_status == "delivered":
        if not task.finished_at:
            task.finished_at = now_iso
        task.delivered_at = now_iso
        return
    if new_status == "finished":
        if not task.finished_at:
            task.finished_at = now_iso
        task.delivered_at = None
        return
    task.finished_at = None
    task.delivered_at = None


async def create_task(session: AsyncSession, **kwargs) -> tuple[Task, bool]:
    """Create a new task and initial status log.

    Returns (task, created) where created=False means an existing task
    for the same (chat_id, message_id) was returned after a race.
    """
    task = Task(**kwargs)
    session.add(task)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        chat_id = kwargs.get("chat_id")
        message_id = kwargs.get("message_id")
        if chat_id is not None and message_id is not None:
            existing = await get_task_by_message(session, chat_id, message_id)
            if existing:
                logger.warning(
                    "task_create_duplicate",
                    task_id=existing.id,
                    chat_id=chat_id,
                    message_id=message_id,
                )
                return existing, False
        raise

    log = StatusLog(
        task_id=task.id,
        from_status=None,
        to_status=task.status,
        changed_by_name="bot",
        note="auto-detected" if kwargs.get("ai_confidence") else "manual",
    )
    session.add(log)
    await session.flush()

    logger.info("task_created", task_id=task.id, status=task.status)
    return task, True


async def get_task_by_id(session: AsyncSession, task_id: int) -> Task | None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    return result.scalar_one_or_none()


async def get_task_by_message(
    session: AsyncSession, chat_id: int, message_id: int
) -> Task | None:
    result = await session.execute(
        select(Task).where(Task.chat_id == chat_id, Task.message_id == message_id)
    )
    return result.scalar_one_or_none()


async def get_task_by_bot_message(
    session: AsyncSession, chat_id: int, bot_message_id: int
) -> Task | None:
    result = await session.execute(
        select(Task).where(
            Task.chat_id == chat_id, Task.bot_message_id == bot_message_id
        )
    )
    return result.scalar_one_or_none()


async def update_task_status(
    session: AsyncSession,
    task: Task,
    new_status: str,
    changed_by_id: int | None = None,
    changed_by_name: str | None = None,
    note: str | None = None,
) -> Task:
    """Update task status with validation and audit log."""
    allowed = VALID_TRANSITIONS.get(task.status, [])
    if new_status not in allowed:
        raise InvalidTransitionError(task.status, new_status, allowed)

    old_status = task.status
    now_iso = datetime.now(timezone.utc).isoformat()
    task.status = new_status
    task.updated_at = now_iso
    _apply_status_timestamps(task, new_status, now_iso)

    log = StatusLog(
        task_id=task.id,
        from_status=old_status,
        to_status=new_status,
        changed_by_id=changed_by_id,
        changed_by_name=changed_by_name,
        note=note,
    )
    session.add(log)
    await session.flush()

    logger.info(
        "task_status_updated",
        task_id=task.id,
        from_status=old_status,
        to_status=new_status,
        by=changed_by_name,
    )
    return task


async def force_update_task_status(
    session: AsyncSession,
    task: Task,
    new_status: str,
    changed_by_id: int | None = None,
    changed_by_name: str | None = None,
    note: str | None = None,
) -> Task:
    old_status = task.status
    now_iso = datetime.now(timezone.utc).isoformat()
    task.status = new_status
    task.updated_at = now_iso
    _apply_status_timestamps(task, new_status, now_iso)

    log = StatusLog(
        task_id=task.id,
        from_status=old_status,
        to_status=new_status,
        changed_by_id=changed_by_id,
        changed_by_name=changed_by_name,
        note=note or "forced_status_update",
    )
    session.add(log)
    await session.flush()

    logger.info(
        "task_status_force_updated",
        task_id=task.id,
        from_status=old_status,
        to_status=new_status,
        by=changed_by_name,
    )
    return task


async def update_task_bot_message_id(
    session: AsyncSession, task: Task, bot_message_id: int
) -> None:
    task.bot_message_id = bot_message_id
    await session.flush()


async def update_task_deadline(
    session: AsyncSession,
    task: Task,
    new_deadline: str,
    changed_by_id: int | None = None,
    changed_by_name: str | None = None,
) -> Task:
    old_deadline = task.deadline
    task.deadline = new_deadline
    task.updated_at = datetime.now(timezone.utc).isoformat()

    log = StatusLog(
        task_id=task.id,
        from_status=task.status,
        to_status=task.status,
        changed_by_id=changed_by_id,
        changed_by_name=changed_by_name,
        note=f"deadline: {old_deadline} → {new_deadline}",
    )
    session.add(log)
    await session.flush()
    return task


async def update_task_priority(
    session: AsyncSession,
    task: Task,
    new_priority: str,
    changed_by_id: int | None = None,
    changed_by_name: str | None = None,
) -> Task:
    old_priority = task.priority
    task.priority = new_priority
    task.updated_at = datetime.now(timezone.utc).isoformat()

    log = StatusLog(
        task_id=task.id,
        from_status=task.status,
        to_status=task.status,
        changed_by_id=changed_by_id,
        changed_by_name=changed_by_name,
        note=f"priority: {old_priority} → {new_priority}",
    )
    session.add(log)
    await session.flush()
    return task


async def delete_task(session: AsyncSession, task: Task) -> None:
    await session.delete(task)
    await session.flush()
    logger.info("task_deleted", task_id=task.id)


async def get_active_tasks(session: AsyncSession) -> list[Task]:
    result = await session.execute(
        select(Task)
        .where(Task.status.notin_(["delivered", "cancelled"]))
        .order_by(Task.deadline.asc().nullslast(), Task.created_at.asc())
    )
    return list(result.scalars().all())


async def get_tasks_by_status(session: AsyncSession, status: str) -> list[Task]:
    result = await session.execute(
        select(Task)
        .where(Task.status == status)
        .order_by(Task.deadline.asc().nullslast())
    )
    return list(result.scalars().all())


async def get_overdue_tasks(
    session: AsyncSession, today: str | None = None
) -> list[Task]:
    if today is None:
        today = today_local()
    result = await session.execute(
        select(Task)
        .where(
            Task.deadline.isnot(None),
            Task.deadline < today,
            Task.status.notin_(["finished", "delivered", "cancelled"]),
        )
        .order_by(Task.deadline.asc())
    )
    return list(result.scalars().all())


async def get_tasks_due_soon(
    session: AsyncSession, days: int = 3, today: str | None = None
) -> list[Task]:
    if today is None:
        today_str = today_local()
    else:
        today_str = today
    today_dt = datetime.strptime(today_str, "%Y-%m-%d")
    soon = (today_dt + timedelta(days=days)).strftime("%Y-%m-%d")
    result = await session.execute(
        select(Task)
        .where(
            Task.deadline.isnot(None),
            Task.deadline >= today_str,
            Task.deadline <= soon,
            Task.status.notin_(["finished", "delivered", "cancelled"]),
        )
        .order_by(Task.deadline.asc())
    )
    return list(result.scalars().all())


async def get_all_tasks(session: AsyncSession) -> list[Task]:
    result = await session.execute(
        select(Task).order_by(Task.created_at.desc())
    )
    return list(result.scalars().all())


async def get_finished_tasks_older_than_hours(
    session: AsyncSession, hours: int
) -> list[Task]:
    if hours <= 0:
        hours = 24

    cutoff = datetime.now(timezone.utc).timestamp() - (hours * 3600)
    result = await session.execute(
        select(Task)
        .where(Task.status == "finished", Task.finished_at.isnot(None))
        .order_by(Task.finished_at.asc())
    )
    tasks = list(result.scalars().all())

    overdue: list[Task] = []
    for task in tasks:
        if not task.finished_at:
            continue
        try:
            finished_at = datetime.fromisoformat(task.finished_at).timestamp()
        except ValueError:
            continue
        if finished_at <= cutoff:
            overdue.append(task)
    return overdue


async def get_task_with_logs(
    session: AsyncSession, task_id: int
) -> Task | None:
    """Get task with eagerly loaded status_logs (avoids async lazy-load)."""
    result = await session.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.status_logs))
    )
    return result.scalar_one_or_none()


async def get_recent_tasks(
    session: AsyncSession, limit: int = 5
) -> list[Task]:
    """Get recently updated active tasks for dashboard."""
    result = await session.execute(
        select(Task)
        .where(Task.status.notin_(["delivered", "cancelled"]))
        .order_by(Task.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
