"""Pure text utilities used across the project."""

from html import escape as _html_escape


def esc(text: str | None) -> str:
    """Escape text for Telegram HTML parse mode."""
    if not text:
        return ""
    return _html_escape(str(text), quote=False)


def normalize_username(username: str | None) -> str | None:
    if username is None:
        return None
    normalized = username.strip().lstrip("@").lower()
    return normalized or None


def compact_preview(text: str | None, limit: int = 120) -> str | None:
    if not text:
        return None
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def user_display_name(user) -> str:
    """Format a Telegram User for display. Accepts aiogram User or None."""
    if not user:
        return "Пользователь"
    return f"@{user.username}" if user.username else user.full_name
