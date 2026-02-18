"""Jinja2 template filters wrapping ui/formatters.py for web use.

The Telegram formatters use esc() (html.escape) for Telegram HTML parse mode.
Jinja2 autoescape handles HTML escaping itself, so web filters must NOT
double-escape. Most formatters are safe as-is; format_amount() needs a
web-safe wrapper that skips esc().
"""

from datetime import datetime

from jinja2 import Environment

from ui.formatters import (
    PRIORITY_EMOJI,
    STATUS_EMOJI,
    STATUS_LABEL,
    format_days_overdue,
    format_deadline_status,
)

MONTH_NAMES_RU = [
    "",  # 0-indexed placeholder
    "Январь", "Февраль", "Март", "Апрель",
    "Май", "Июнь", "Июль", "Август",
    "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

STATUS_COLOR = {
    "draft": "neutral",
    "awaiting_confirmation": "info",
    "processing": "warning",
    "finished": "secondary",
    "delivered": "success",
    "cancelled": "error",
}

STATUS_BORDER_COLOR = {
    "draft": "border-gray-400",
    "awaiting_confirmation": "border-blue-400",
    "processing": "border-yellow-400",
    "finished": "border-purple-400",
    "delivered": "border-green-400",
    "cancelled": "border-red-400",
}

PLATFORM_LABEL = {
    "fansly": "Fansly",
    "onlyfans": "OnlyFans",
}


def web_format_amount(amount_total: float | None, payment_note: str | None = None) -> str:
    """Web-safe version of format_amount — no esc() call.

    Jinja2 autoescape will handle escaping payment_note in the template.
    """
    if amount_total is None:
        return "—"
    amount_str = f"${amount_total:.0f}"
    if payment_note:
        amount_str += f" ({payment_note})"
    return amount_str


def web_format_datetime(iso_str: str | None) -> str:
    """Format ISO datetime string to human-readable Russian format."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso_str


def web_format_date(date_str: str | None) -> str:
    """Format YYYY-MM-DD date to DD.MM.YYYY."""
    if not date_str:
        return "—"
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return date_str


def register_filters(env: Environment) -> None:
    """Register all custom Jinja2 template filters."""
    env.filters["status_emoji"] = lambda s: STATUS_EMOJI.get(s, "")
    env.filters["status_label"] = lambda s: STATUS_LABEL.get(s, s)
    env.filters["status_color"] = lambda s: STATUS_COLOR.get(s, "neutral")
    env.filters["status_border"] = lambda s: STATUS_BORDER_COLOR.get(s, "border-gray-400")
    env.filters["priority_emoji"] = lambda p: PRIORITY_EMOJI.get(p, "")
    env.filters["platform_label"] = lambda p: PLATFORM_LABEL.get(p, p or "—")
    env.filters["format_amount"] = web_format_amount
    env.filters["format_deadline"] = format_deadline_status
    env.filters["format_overdue"] = format_days_overdue
    env.filters["format_datetime"] = web_format_datetime
    env.filters["format_date"] = web_format_date
    env.filters["month_name"] = lambda m: MONTH_NAMES_RU[m] if 1 <= m <= 12 else str(m)

    # Global variables available in all templates
    env.globals["STATUS_EMOJI"] = STATUS_EMOJI
    env.globals["STATUS_LABEL"] = STATUS_LABEL
    env.globals["PRIORITY_EMOJI"] = PRIORITY_EMOJI
