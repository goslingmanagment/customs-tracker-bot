"""Task creation helpers — single place for AI data sanitization and kwargs assembly."""

from datetime import datetime

from core.brief_text_parser import parse_original_brief_sections
from core.constants import VALID_PRIORITIES
from db.repo import task_repo


def sanitize_ai_data(data: dict) -> dict:
    """Ensure constrained fields have valid values. Mutates and returns data."""
    if data.get("priority") not in VALID_PRIORITIES:
        data["priority"] = "medium"

    raw_deadline = data.get("deadline")
    if raw_deadline:
        try:
            datetime.strptime(raw_deadline, "%Y-%m-%d")
        except (ValueError, TypeError):
            data["deadline"] = None

    return data


def build_task_kwargs(
    data: dict,
    *,
    message_id: int,
    chat_id: int,
    topic_id: int | None,
    raw_text: str,
    ai_confidence: float,
    sender_username: str | None,
) -> dict:
    """Build the kwargs dict for task_repo.create_task from AI classification data."""
    original_sections = parse_original_brief_sections(raw_text)

    return {
        "message_id": message_id,
        "chat_id": chat_id,
        "topic_id": topic_id,
        "raw_text": raw_text,
        "ai_confidence": ai_confidence,
        "sender_username": sender_username,
        "task_date": data.get("task_date"),
        "fan_link": data.get("fan_link"),
        "fan_name": data.get("fan_name"),
        "platform": data.get("platform"),
        "amount_total": data.get("amount_total"),
        "amount_paid": data.get("amount_paid"),
        "amount_remaining": data.get("amount_remaining"),
        "payment_note": data.get("payment_note"),
        "duration": data.get("duration"),
        "description": data.get("description"),
        "outfit": data.get("outfit"),
        "notes": data.get("notes"),
        "description_original": original_sections["description_original"],
        "outfit_original": original_sections["outfit_original"],
        "notes_original": original_sections["notes_original"],
        "priority": data.get("priority", "medium"),
        "deadline": data.get("deadline"),
    }
