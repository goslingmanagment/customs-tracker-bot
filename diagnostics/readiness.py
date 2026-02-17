"""Health checks for environment and runtime configuration."""

from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram.utils.token import TokenValidationError, validate_token

from core.config import env, runtime
from core.exceptions import StartupConfigError


# --- Blocker / warning codes ---

BLOCKER_BOT_TOKEN_MISSING = "bot_token_missing"
BLOCKER_BOT_TOKEN_INVALID_FORMAT = "bot_token_invalid_format"
BLOCKER_ANTHROPIC_API_KEY_MISSING = "anthropic_api_key_missing"
BLOCKER_RUNTIME_SETTINGS_MISSING = "runtime_settings_missing"
BLOCKER_CUSTOMS_CHAT_ID_MISSING = "customs_chat_id_missing"
BLOCKER_CUSTOMS_TOPIC_ID_MISSING = "customs_topic_id_missing"
BLOCKER_AI_MODEL_MISSING = "ai_model_missing"
BLOCKER_TIMEZONE_INVALID = "timezone_invalid"

WARNING_AI_CONFIDENCE_THRESHOLD_RANGE = "ai_confidence_threshold_out_of_range"
WARNING_REMINDER_HOURS_BEFORE_INVALID = "reminder_hours_before_invalid"
WARNING_OVERDUE_REMINDER_COOLDOWN_HOURS_INVALID = "overdue_reminder_cooldown_hours_invalid"
WARNING_HIGH_URGENCY_COOLDOWN_HOURS_INVALID = "high_urgency_cooldown_hours_invalid"
WARNING_FINISHED_REMINDER_HOURS_INVALID = "finished_reminder_hours_invalid"

_STARTUP_FATAL_BLOCKERS = {
    BLOCKER_BOT_TOKEN_MISSING,
    BLOCKER_BOT_TOKEN_INVALID_FORMAT,
    BLOCKER_ANTHROPIC_API_KEY_MISSING,
}
_STARTUP_FATAL_DETAILS = {
    BLOCKER_BOT_TOKEN_MISSING: "BOT_TOKEN is missing.",
    BLOCKER_BOT_TOKEN_INVALID_FORMAT: "BOT_TOKEN format is invalid (expected <digits>:<secret>).",
    BLOCKER_ANTHROPIC_API_KEY_MISSING: "ANTHROPIC_API_KEY is missing.",
}


@dataclass(slots=True)
class BriefEnvReadiness:
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.blockers


@dataclass(slots=True)
class StartupReadiness:
    readiness: BriefEnvReadiness
    fatal_blockers: list[str] = field(default_factory=list)
    non_fatal_blockers: list[str] = field(default_factory=list)

    @property
    def can_start(self) -> bool:
        return not self.fatal_blockers


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def _is_bot_token_format_valid(value: str | None) -> bool:
    if _is_blank(value):
        return False
    try:
        validate_token(value.strip())
    except TokenValidationError:
        return False
    return True


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and value > 0


def evaluate_brief_env_readiness() -> BriefEnvReadiness:
    """Check if the bot is ready to process briefs. Uses module-level singletons."""
    readiness = BriefEnvReadiness()

    bot_token = env.bot_token or ""
    if _is_blank(bot_token):
        readiness.blockers.append(BLOCKER_BOT_TOKEN_MISSING)
    elif not _is_bot_token_format_valid(bot_token):
        readiness.blockers.append(BLOCKER_BOT_TOKEN_INVALID_FORMAT)

    if _is_blank(env.anthropic_api_key):
        readiness.blockers.append(BLOCKER_ANTHROPIC_API_KEY_MISSING)

    if runtime.customs_chat_id == 0:
        readiness.blockers.append(BLOCKER_CUSTOMS_CHAT_ID_MISSING)
    if runtime.customs_topic_id == 0:
        readiness.blockers.append(BLOCKER_CUSTOMS_TOPIC_ID_MISSING)
    if not (runtime.ai_model or "").strip():
        readiness.blockers.append(BLOCKER_AI_MODEL_MISSING)

    timezone_name = (runtime.timezone or "").strip()
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        readiness.blockers.append(BLOCKER_TIMEZONE_INVALID)

    threshold = runtime.ai_confidence_threshold
    if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
        readiness.warnings.append(WARNING_AI_CONFIDENCE_THRESHOLD_RANGE)

    if not _is_positive_int(runtime.reminder_hours_before):
        readiness.warnings.append(WARNING_REMINDER_HOURS_BEFORE_INVALID)
    if not _is_positive_int(runtime.overdue_reminder_cooldown_hours):
        readiness.warnings.append(WARNING_OVERDUE_REMINDER_COOLDOWN_HOURS_INVALID)
    if not _is_positive_int(runtime.high_urgency_cooldown_hours):
        readiness.warnings.append(WARNING_HIGH_URGENCY_COOLDOWN_HOURS_INVALID)
    if not _is_positive_int(runtime.finished_reminder_hours):
        readiness.warnings.append(WARNING_FINISHED_REMINDER_HOURS_INVALID)

    return readiness


def evaluate_startup_readiness() -> StartupReadiness:
    readiness = evaluate_brief_env_readiness()
    fatal: list[str] = []
    non_fatal: list[str] = []

    for blocker in readiness.blockers:
        if blocker in _STARTUP_FATAL_BLOCKERS:
            fatal.append(blocker)
        else:
            non_fatal.append(blocker)

    return StartupReadiness(
        readiness=readiness,
        fatal_blockers=fatal,
        non_fatal_blockers=non_fatal,
    )


def build_startup_config_error(startup: StartupReadiness) -> StartupConfigError:
    detail_codes = startup.fatal_blockers or [BLOCKER_BOT_TOKEN_INVALID_FORMAT]
    details = [_STARTUP_FATAL_DETAILS.get(code, code) for code in detail_codes]
    hints = [
        "Set BOT_TOKEN in .env to the real token from @BotFather.",
        "Expected format: <digits>:<secret> (example: 123456789:AA...)",
        "Set ANTHROPIC_API_KEY in .env.",
        "Restart the bot: uv run python bot.py",
    ]
    return StartupConfigError(
        code="startup_config_invalid",
        title="Startup configuration is invalid.",
        details=details,
        hints=hints,
        exit_code=2,
    )


def summarize_readiness_for_log(readiness: BriefEnvReadiness) -> dict[str, Any]:
    return {
        "ready": readiness.ready,
        "blockers": readiness.blockers,
        "warnings": readiness.warnings,
        "blocker_count": len(readiness.blockers),
        "warning_count": len(readiness.warnings),
        "bot_token_set": bool(env.bot_token),
        "customs_chat_id": runtime.customs_chat_id,
        "customs_topic_id": runtime.customs_topic_id,
        "anthropic_api_key_set": bool(env.anthropic_api_key),
        "ai_model_set": bool((runtime.ai_model or "").strip()),
        "timezone": runtime.timezone,
    }
