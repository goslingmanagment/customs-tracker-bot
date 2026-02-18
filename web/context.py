"""Jinja2 template filters wrapping ui/formatters.py for web use.

The Telegram formatters use esc() (html.escape) for Telegram HTML parse mode.
Jinja2 autoescape handles HTML escaping itself, so web filters must NOT
double-escape. Most formatters are safe as-is; format_amount() needs a
web-safe wrapper that skips esc().
"""

from datetime import datetime

from jinja2 import Environment

from core.log_utils import today_local
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
    "draft": "border-border-light",
    "awaiting_confirmation": "border-status-blue/40",
    "processing": "border-status-amber/40",
    "finished": "border-status-purple/40",
    "delivered": "border-status-green/40",
    "cancelled": "border-status-red/40",
}

STATUS_BADGE = {
    "draft": "bg-[rgba(120,117,108,0.07)] text-[#78756c]",
    "awaiting_confirmation": "bg-[rgba(74,127,181,0.07)] text-[#4a7fb5]",
    "processing": "bg-[rgba(160,120,48,0.07)] text-[#a07830]",
    "finished": "bg-[rgba(124,106,155,0.07)] text-[#7c6a9b]",
    "delivered": "bg-[rgba(74,138,92,0.07)] text-[#4a8a5c]",
    "cancelled": "bg-[rgba(181,86,78,0.07)] text-[#b5564e]",
}

PLATFORM_LABEL = {
    "fansly": "Fansly",
    "onlyfans": "OnlyFans",
}

DEADLINE_URGENCY = {
    "overdue": {
        "card":  "border-l-[3px] border-l-[#b5564e]",
        "badge": "bg-[rgba(181,86,78,0.10)] text-[#b5564e] font-medium",
        "text":  "text-[#b5564e] font-medium",
    },
    "critical": {
        "card":  "border-l-[3px] border-l-[#b5564e]",
        "badge": "bg-[rgba(181,86,78,0.07)] text-[#b5564e]",
        "text":  "text-[#b5564e] font-medium",
    },
    "warning": {
        "card":  "border-l-[3px] border-l-[#a07830]",
        "badge": "bg-[rgba(160,120,48,0.07)] text-[#a07830]",
        "text":  "text-[#a07830]",
    },
    "soon": {
        "card":  "border-l-[3px] border-l-[#c4bda8]",
        "badge": "",
        "text":  "text-ink-secondary",
    },
    "normal": {"card": "", "badge": "", "text": "text-ink-tertiary"},
    "none":   {"card": "", "badge": "", "text": "text-ink-muted"},
}


def _deadline_urgency(deadline: str | None) -> str:
    """Return urgency tier name for a deadline string."""
    if not deadline:
        return "none"
    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return "none"
    today = datetime.strptime(today_local(), "%Y-%m-%d").date()
    days_left = (deadline_date - today).days
    if days_left < 0:
        return "overdue"
    if days_left <= 1:
        return "critical"
    if days_left <= 3:
        return "warning"
    if days_left <= 7:
        return "soon"
    return "normal"


def web_deadline_text(deadline: str | None) -> str:
    """Clean deadline display text for the web UI (no emojis)."""
    if not deadline:
        return ""
    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return deadline
    today = datetime.strptime(today_local(), "%Y-%m-%d").date()
    days_left = (deadline_date - today).days
    if days_left < 0:
        n = abs(days_left)
        if n == 1:
            return "просрочено на 1 день"
        if n < 5:
            return f"просрочено на {n} дня"
        return f"просрочено на {n} дней"
    if days_left == 0:
        return "сегодня"
    if days_left == 1:
        return "завтра"
    if days_left < 5:
        return f"через {days_left} дня"
    return f"до {deadline_date.strftime('%d.%m')}"


def web_deadline_css(deadline: str | None) -> str:
    """Tailwind CSS classes for deadline text color."""
    return DEADLINE_URGENCY[_deadline_urgency(deadline)]["text"]


def web_deadline_card_css(deadline: str | None) -> str:
    """Tailwind CSS classes for card-level urgency (left border accent)."""
    return DEADLINE_URGENCY[_deadline_urgency(deadline)]["card"]


def web_deadline_badge_css(deadline: str | None) -> str:
    """Tailwind CSS classes for deadline pill badge (bg + text)."""
    return DEADLINE_URGENCY[_deadline_urgency(deadline)]["badge"]


def web_deadline_counter(deadline: str | None) -> dict:
    """Return a dict with big-number countdown data for the card display.

    Keys: number (str), label (str), css (str for the number color),
          show (bool — whether to render the counter at all).
    """
    if not deadline:
        return {"show": False, "number": "", "label": "", "css": ""}
    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return {"show": False, "number": "", "label": "", "css": ""}
    today = datetime.strptime(today_local(), "%Y-%m-%d").date()
    days_left = (deadline_date - today).days
    urgency = _deadline_urgency(deadline)
    css = DEADLINE_URGENCY[urgency]["text"]
    if days_left < 0:
        n = abs(days_left)
        return {"show": True, "number": f"+{n}", "label": "просрочено", "css": css}
    if days_left == 0:
        return {"show": True, "number": "0", "label": "сегодня", "css": css}
    if days_left <= 7:
        if days_left == 1:
            label = "день"
        elif days_left < 5:
            label = "дня"
        else:
            label = "дней"
        return {"show": True, "number": str(days_left), "label": label, "css": css}
    return {"show": False, "number": str(days_left), "label": "дней", "css": css}


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
    env.filters["status_badge"] = lambda s: STATUS_BADGE.get(s, "bg-gray-500/10 text-gray-400")
    env.filters["priority_emoji"] = lambda p: PRIORITY_EMOJI.get(p, "")
    env.filters["platform_label"] = lambda p: PLATFORM_LABEL.get(p, p or "—")
    env.filters["format_amount"] = web_format_amount
    env.filters["format_deadline"] = format_deadline_status
    env.filters["format_overdue"] = format_days_overdue
    env.filters["deadline_text"] = web_deadline_text
    env.filters["deadline_css"] = web_deadline_css
    env.filters["deadline_card_css"] = web_deadline_card_css
    env.filters["deadline_badge_css"] = web_deadline_badge_css
    env.filters["deadline_counter"] = web_deadline_counter
    env.filters["format_datetime"] = web_format_datetime
    env.filters["format_date"] = web_format_date
    env.filters["month_name"] = lambda m: MONTH_NAMES_RU[m] if 1 <= m <= 12 else str(m)

    # Global variables available in all templates
    env.globals["STATUS_EMOJI"] = STATUS_EMOJI
    env.globals["STATUS_LABEL"] = STATUS_LABEL
    env.globals["PRIORITY_EMOJI"] = PRIORITY_EMOJI
