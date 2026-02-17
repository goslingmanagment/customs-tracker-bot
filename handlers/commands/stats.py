from datetime import datetime, timezone

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.permissions import is_admin
from db.engine import async_session
from handlers.filters import WorkingTopicFilter
from services.role_service import resolve_admin_identity
from services.stats_service import get_monthly_stats

logger = structlog.get_logger()

router = Router()


@router.message(Command("stats"), WorkingTopicFilter())
async def cmd_stats(message: Message):
    if not is_admin(message.from_user):
        await message.reply("Доступно только администраторам")
        return

    async with async_session() as session:
        await resolve_admin_identity(message.from_user, session)

    now = datetime.now(timezone.utc)
    year, month = now.year, now.month

    args = (message.text or "").split(maxsplit=1)
    if len(args) > 1:
        month_names = {
            "январь": 1, "january": 1, "jan": 1,
            "февраль": 2, "february": 2, "feb": 2,
            "март": 3, "march": 3, "mar": 3,
            "апрель": 4, "april": 4, "apr": 4,
            "май": 5, "may": 5,
            "июнь": 6, "june": 6, "jun": 6,
            "июль": 7, "july": 7, "jul": 7,
            "август": 8, "august": 8, "aug": 8,
            "сентябрь": 9, "september": 9, "sep": 9,
            "октябрь": 10, "october": 10, "oct": 10,
            "ноябрь": 11, "november": 11, "nov": 11,
            "декабрь": 12, "december": 12, "dec": 12,
        }
        arg = args[1].strip().lower()
        if arg in month_names:
            month = month_names[arg]

    async with async_session() as session:
        stats = await get_monthly_stats(session, year, month)

    month_names_ru = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]

    lines = [
        f"📊 <b>Статистика за {month_names_ru[month]} {year}</b>\n",
        f"Всего кастомов: {stats['total']}",
        f"Выполнено: {stats['completed']}",
        f"В работе: {stats['in_progress']}",
        f"Отснято: {stats['finished']}",
        f"Отменено: {stats['cancelled']}",
        "",
        f"💰 Общая сумма: ${stats['total_amount']:.0f}",
        f"💰 Средний чек: ${stats['avg_amount']:.0f}",
        "",
        f"📉 Просрочено: {stats['overdue']}",
    ]

    if stats["platforms"]:
        lines.append("\nПлатформы:")
        for platform, data in stats["platforms"].items():
            lines.append(f"  {platform}: {data['count']} (${data['amount']:.0f})")

    await message.reply("\n".join(lines))
