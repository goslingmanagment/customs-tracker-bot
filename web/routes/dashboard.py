"""Dashboard route — overview with counters, overdue, and due-soon tasks."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.repo import task_repo
from services.stats_service import get_monthly_stats
from web.deps import get_current_user, get_session

router = APIRouter()


@router.get("/")
async def dashboard(
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    templates = request.app.state.templates

    # Gather data
    active_tasks = await task_repo.get_active_tasks(session)
    overdue_tasks = await task_repo.get_overdue_tasks(session)
    due_soon_tasks = await task_repo.get_tasks_due_soon(session, days=3)
    recent_tasks = await task_repo.get_recent_tasks(session, limit=5)

    now = datetime.now()
    stats = await get_monthly_stats(session, now.year, now.month)

    processing_count = sum(1 for t in active_tasks if t.status == "processing")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "active_page": "dashboard",
            "active_count": len(active_tasks),
            "overdue_count": len(overdue_tasks),
            "processing_count": processing_count,
            "month_amount": stats["total_amount"],
            "overdue_tasks": overdue_tasks,
            "due_soon_tasks": due_soon_tasks,
            "recent_tasks": recent_tasks,
        },
    )
