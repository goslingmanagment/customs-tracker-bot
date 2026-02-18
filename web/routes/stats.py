"""Stats route — monthly analytics."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from services.stats_service import get_monthly_stats
from web.deps import get_session, require_role

router = APIRouter()


def _prev_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


@router.get("/stats")
async def stats_page(
    request: Request,
    user: dict = Depends(require_role("admin", "teamlead")),
    session: AsyncSession = Depends(get_session),
):
    templates = request.app.state.templates
    now = datetime.now()
    year, month = now.year, now.month
    stats = await get_monthly_stats(session, year, month)

    prev_y, prev_m = _prev_month(year, month)
    is_current = True

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "user": user,
            "active_page": "stats",
            "stats": stats,
            "year": year,
            "month": month,
            "prev_year": prev_y,
            "prev_month": prev_m,
            "is_current_month": is_current,
        },
    )


@router.get("/htmx/stats/{year}/{month}")
async def htmx_stats(
    request: Request,
    year: int,
    month: int,
    user: dict = Depends(require_role("admin", "teamlead")),
    session: AsyncSession = Depends(get_session),
):
    """HTMX partial: returns stats grid for a specific month."""
    templates = request.app.state.templates

    if month < 1 or month > 12:
        month = 1

    stats = await get_monthly_stats(session, year, month)

    prev_y, prev_m = _prev_month(year, month)
    next_y, next_m = _next_month(year, month)

    now = datetime.now()
    is_current = (year == now.year and month == now.month)

    return templates.TemplateResponse(
        "partials/stats_grid.html",
        {
            "request": request,
            "user": user,
            "stats": stats,
            "year": year,
            "month": month,
            "prev_year": prev_y,
            "prev_month": prev_m,
            "next_year": next_y,
            "next_month": next_m,
            "is_current_month": is_current,
        },
    )
