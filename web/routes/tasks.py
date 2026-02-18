"""Task list and detail routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.repo import task_repo
from web.deps import get_current_user, get_session

router = APIRouter()

# Status filter presets
_STATUS_FILTERS = {
    "all": None,
    "active": None,  # special: non-delivered, non-cancelled
    "overdue": None,  # special: overdue tasks
    "draft": "draft",
    "awaiting_confirmation": "awaiting_confirmation",
    "processing": "processing",
    "finished": "finished",
    "delivered": "delivered",
    "cancelled": "cancelled",
}


async def _get_filtered_tasks(session: AsyncSession, status_filter: str):
    """Get tasks filtered by status preset."""
    if status_filter == "overdue":
        return await task_repo.get_overdue_tasks(session)
    elif status_filter == "active" or status_filter == "all":
        if status_filter == "active":
            return await task_repo.get_active_tasks(session)
        return await task_repo.get_all_tasks(session)
    elif status_filter in _STATUS_FILTERS and _STATUS_FILTERS[status_filter]:
        return await task_repo.get_tasks_by_status(session, _STATUS_FILTERS[status_filter])
    else:
        return await task_repo.get_active_tasks(session)


@router.get("/tasks")
async def task_list(
    request: Request,
    status: str = "active",
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    templates = request.app.state.templates
    tasks = await _get_filtered_tasks(session, status)

    return templates.TemplateResponse(
        "task_list.html",
        {
            "request": request,
            "user": user,
            "active_page": "tasks",
            "tasks": tasks,
            "current_filter": status,
            "task_count": len(tasks),
        },
    )


@router.get("/htmx/tasks")
async def htmx_task_grid(
    request: Request,
    status: str = "active",
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """HTMX partial: returns just the task card grid."""
    templates = request.app.state.templates
    tasks = await _get_filtered_tasks(session, status)

    return templates.TemplateResponse(
        "partials/task_grid.html",
        {
            "request": request,
            "user": user,
            "tasks": tasks,
            "current_filter": status,
            "task_count": len(tasks),
        },
    )


@router.get("/tasks/{task_id}")
async def task_detail(
    request: Request,
    task_id: int,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    templates = request.app.state.templates
    task = await task_repo.get_task_with_logs(session, task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # Sort logs chronologically (newest first)
    logs = sorted(task.status_logs, key=lambda l: l.created_at, reverse=True)

    return templates.TemplateResponse(
        "task_detail.html",
        {
            "request": request,
            "user": user,
            "active_page": "tasks",
            "task": task,
            "logs": logs,
        },
    )
