"""Quick heuristic to decide if a message might be a brief (no AI)."""

import re

from aiogram.types import Message

from core.constants import (
    BRIEF_EMOJIS,
    BRIEF_KEYWORDS,
    DIRECT_MARKERS,
    MIN_BRIEF_TEXT_LENGTH,
    MIN_HEURISTIC_SCORE,
)
from core.permissions import is_teamlead

PLATFORM_PATTERN = re.compile(r"(fansly\.com|onlyfans\.com)", re.IGNORECASE)


def evaluate_message_for_processing(message: Message) -> tuple[bool, str, dict[str, object]]:
    """
    Evaluate whether a message should be sent to AI.
    Returns: (should_process, reason, details)
    """
    text = message.text or message.caption
    username = message.from_user.username if message.from_user else None

    if not text:
        return False, "no_text", {"text_len": 0, "sender_username": username}

    details: dict[str, object] = {
        "text_len": len(text),
        "sender_username": username,
    }

    if message.forward_date:
        return False, "forwarded", details

    if is_teamlead(message.from_user):
        return True, "teamlead_sender", details

    if len(text) < MIN_BRIEF_TEXT_LENGTH:
        return False, "too_short", details

    text_lower = text.lower()

    direct_marker = next((m for m in DIRECT_MARKERS if m in text_lower), None)
    has_emoji = any(emoji in text for emoji in BRIEF_EMOJIS)
    has_keyword = any(kw in text_lower for kw in BRIEF_KEYWORDS)
    has_platform_link = bool(PLATFORM_PATTERN.search(text))
    has_payment_marker = "$" in text or "минут" in text_lower

    score = 0
    if len(text) > 100:
        score += 1
    if has_emoji:
        score += 1
    if has_keyword:
        score += 1
    if has_platform_link:
        score += 1
    if has_payment_marker:
        score += 1

    details.update({
        "score": score,
        "has_direct_marker": bool(direct_marker),
        "has_emoji": has_emoji,
        "has_keyword": has_keyword,
        "has_platform_link": has_platform_link,
        "has_payment_marker": has_payment_marker,
    })

    if direct_marker:
        details["direct_marker"] = direct_marker
        return True, "direct_marker", details

    if score >= MIN_HEURISTIC_SCORE:
        return True, "heuristic_score", details

    return False, "heuristic_score_low", details
