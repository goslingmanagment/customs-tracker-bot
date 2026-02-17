"""Shared logging helpers."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram.types import Message

from core.config import runtime


def now_iso() -> str:
    """Current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def today_local() -> str:
    """Today's date in YYYY-MM-DD using the configured timezone."""
    return datetime.now(ZoneInfo(runtime.timezone)).strftime("%Y-%m-%d")


def message_log_context(message: Message, text: str | None = None) -> dict[str, object]:
    """Build a common log context dict from a Telegram message."""
    payload = text if text is not None else (message.text or message.caption or "")
    user = message.from_user
    return {
        "message_id": message.message_id,
        "chat_id": message.chat.id,
        "topic_id": message.message_thread_id,
        "reply_to_message_id": (
            message.reply_to_message.message_id if message.reply_to_message else None
        ),
        "from_user_id": user.id if user else None,
        "from_username": user.username if user else None,
        "has_text": bool(payload),
        "text_len": len(payload),
        "has_photo": bool(message.photo),
    }
