from datetime import datetime

from core.log_utils import today_local
from core.text_utils import esc

STATUS_EMOJI = {
    "draft": "📋",
    "awaiting_confirmation": "📦",
    "processing": "🎬",
    "finished": "📹",
    "delivered": "✔️",
    "cancelled": "🗑",
}

STATUS_LABEL = {
    "draft": "ЧЕРНОВИК",
    "awaiting_confirmation": "ОЖИДАЕТ МОДЕЛЬ",
    "processing": "В РАБОТЕ",
    "finished": "ОТСНЯТО",
    "delivered": "ВЫПОЛНЕНО",
    "cancelled": "ОТМЕНЁН",
}

PRIORITY_EMOJI = {
    "low": "🟢",
    "medium": "🟡",
    "high": "🔴",
}


def format_deadline_status(deadline: str | None) -> str:
    if not deadline:
        return ""
    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return f"⏰ {deadline}"

    today = datetime.strptime(today_local(), "%Y-%m-%d").date()
    days_left = (deadline_date - today).days

    if days_left < 0:
        return f"🔴 просрочено на {abs(days_left)} дн."
    elif days_left == 0:
        return "🔴 сегодня!"
    elif days_left <= 3:
        return f"⚠️ через {days_left} дн."
    else:
        return f"⏰ до {deadline_date.strftime('%d.%m')}"


def format_amount(amount_total: float | None, payment_note: str | None = None) -> str:
    if amount_total is None:
        return "—"
    amount_str = f"${amount_total:.0f}"
    if payment_note:
        amount_str += f" ({esc(payment_note)})"
    return amount_str


def format_days_overdue(deadline: str | None) -> str:
    if not deadline:
        return ""
    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        return ""

    today = datetime.strptime(today_local(), "%Y-%m-%d").date()
    days = (today - deadline_date).days
    if days <= 0:
        return ""
    if days == 1:
        return "+1 день"
    elif days < 5:
        return f"+{days} дня"
    else:
        return f"+{days} дней"
