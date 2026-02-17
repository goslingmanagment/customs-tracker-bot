"""Claude API integration for brief classification."""

import asyncio
import json
from datetime import datetime
from typing import Any

import anthropic
import structlog

from ai.prompts import CLASSIFIER_SYSTEM_PROMPT
from core.config import env, runtime
from core.constants import (
    AI_API_TIMEOUT,
    AI_MAX_INLINE_RETRIES,
    AI_RETRY_BASE_DELAY,
    AMOUNT_FIELDS,
    TEXT_FIELDS,
    VALID_PLATFORMS,
    VALID_PRIORITIES,
)
from core.exceptions import AIPermanentError, AITransientError

logger = structlog.get_logger()

client = anthropic.AsyncAnthropic(api_key=env.anthropic_api_key)


def _as_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _as_optional_amount(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _as_optional_iso_date(value: Any) -> str | None:
    date_str = _as_optional_text(value)
    if not date_str:
        return None
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    return date_str


def _normalize_classifier_result(payload: Any) -> dict | None:
    if not isinstance(payload, dict):
        logger.error("ai_schema_invalid", reason="payload_not_object")
        return None

    is_task = payload.get("is_task")
    if not isinstance(is_task, bool):
        logger.error("ai_schema_invalid", reason="is_task_not_bool")
        return None

    confidence = payload.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        logger.error("ai_schema_invalid", reason="confidence_not_number")
        return None
    confidence_val = float(confidence)
    if confidence_val < 0 or confidence_val > 1:
        logger.error("ai_schema_invalid", reason="confidence_out_of_range", confidence=confidence_val)
        return None

    if not is_task:
        reason = _as_optional_text(payload.get("reason")) or "not_a_brief"
        return {
            "is_task": False,
            "confidence": confidence_val,
            "reason": reason,
        }

    data = payload.get("data")
    if not isinstance(data, dict):
        logger.error("ai_schema_invalid", reason="task_data_not_object")
        return None

    normalized_data: dict[str, Any] = {
        "task_date": _as_optional_iso_date(data.get("task_date")),
        "deadline": _as_optional_iso_date(data.get("deadline")),
    }

    platform = _as_optional_text(data.get("platform"))
    platform = platform.lower() if platform else None
    normalized_data["platform"] = platform if platform in VALID_PLATFORMS else None

    priority = _as_optional_text(data.get("priority"))
    priority = priority.lower() if priority else None
    normalized_data["priority"] = priority if priority in VALID_PRIORITIES else "medium"

    for key in TEXT_FIELDS:
        normalized_data[key] = _as_optional_text(data.get(key))

    for key in AMOUNT_FIELDS:
        normalized_data[key] = _as_optional_amount(data.get(key))

    return {
        "is_task": True,
        "confidence": confidence_val,
        "data": normalized_data,
    }


async def classify_message(text: str, has_photo: bool = False) -> dict | None:
    """
    Send a message to Claude for classification.

    Returns:
      - parsed JSON dict on success
      - None on permanent failure (malformed AI response)
    Raises:
      - AITransientError on retryable failure (rate-limit, connection)
      - AIPermanentError on non-retryable API error
    """
    user_message = text
    if has_photo:
        user_message = "[Фото/референс прикреплено к сообщению]\n\n" + text

    last_error = None
    raw_response = ""
    for attempt in range(1 + AI_MAX_INLINE_RETRIES):
        try:
            response = await asyncio.wait_for(
                client.messages.create(
                    model=runtime.ai_model,
                    max_tokens=1024,
                    system=CLASSIFIER_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                ),
                timeout=AI_API_TIMEOUT,
            )

            if not response.content:
                logger.error("ai_empty_response")
                return None

            raw_response = getattr(response.content[0], "text", "")
            if not isinstance(raw_response, str):
                logger.error("ai_invalid_response_block")
                return None
            raw_response = raw_response.strip()
            if not raw_response:
                logger.error("ai_empty_response_text")
                return None

            # Strip markdown code blocks if present
            if raw_response.startswith("```"):
                lines = raw_response.splitlines()
                lines = [line for line in lines if not line.strip().startswith("```")]
                raw_response = "\n".join(lines).strip()

            parsed = json.loads(raw_response)
            result = _normalize_classifier_result(parsed)
            if result is None:
                return None

            logger.info(
                "ai_classification",
                is_task=result.get("is_task"),
                confidence=result.get("confidence"),
            )

            return result

        except json.JSONDecodeError as e:
            logger.error("ai_json_parse_error", error=str(e), raw=raw_response[:200])
            return None  # Permanent: AI returned garbage
        except (anthropic.RateLimitError, anthropic.APIConnectionError, asyncio.TimeoutError) as e:
            last_error = e
            delay = AI_RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning(
                "ai_transient_error",
                error=str(e),
                attempt=attempt + 1,
                retry_in=delay,
            )
            if attempt < AI_MAX_INLINE_RETRIES:
                await asyncio.sleep(delay)
            continue
        except anthropic.APIStatusError as e:
            status = int(getattr(e, "status_code", 0) or 0)
            if status >= 500 or status in {408, 409, 429}:
                last_error = e
                delay = AI_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("ai_server_error", status=status, attempt=attempt + 1, retry_in=delay)
                if attempt < AI_MAX_INLINE_RETRIES:
                    await asyncio.sleep(delay)
                continue
            logger.error("ai_api_error_non_retryable", status=status, error=str(e))
            return None
        except Exception as e:
            logger.error("ai_unexpected_error", error=str(e))
            return None

    logger.error("ai_retries_exhausted", error=str(last_error))
    raise AITransientError(str(last_error))
