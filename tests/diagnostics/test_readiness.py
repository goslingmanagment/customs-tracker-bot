from diagnostics import readiness
from core.config import env, runtime


def _set_valid_config():
    env.bot_token = f"123456:{'A' * 35}"
    env.anthropic_api_key = "sk-ant-test"

    runtime.customs_chat_id = -100500
    runtime.customs_topic_id = 777
    runtime.ai_model = "claude-test"
    runtime.ai_confidence_threshold = 0.7
    runtime.reminder_hours_before = 24
    runtime.overdue_reminder_cooldown_hours = 4
    runtime.high_urgency_cooldown_hours = 2
    runtime.finished_reminder_hours = 24
    runtime.timezone = "UTC"


def test_evaluate_brief_env_readiness_detects_missing_values():
    env.bot_token = ""
    env.anthropic_api_key = ""
    runtime.customs_chat_id = 0
    runtime.customs_topic_id = 0
    runtime.ai_model = ""
    runtime.timezone = "No/SuchTimezone"

    result = readiness.evaluate_brief_env_readiness()

    assert readiness.BLOCKER_BOT_TOKEN_MISSING in result.blockers
    assert readiness.BLOCKER_ANTHROPIC_API_KEY_MISSING in result.blockers
    assert readiness.BLOCKER_CUSTOMS_CHAT_ID_MISSING in result.blockers
    assert readiness.BLOCKER_CUSTOMS_TOPIC_ID_MISSING in result.blockers
    assert readiness.BLOCKER_AI_MODEL_MISSING in result.blockers
    assert readiness.BLOCKER_TIMEZONE_INVALID in result.blockers
    assert result.ready is False


def test_evaluate_brief_env_readiness_warning_matrix():
    _set_valid_config()
    runtime.ai_confidence_threshold = 1.5
    runtime.finished_reminder_hours = 0

    result = readiness.evaluate_brief_env_readiness()

    assert readiness.WARNING_AI_CONFIDENCE_THRESHOLD_RANGE in result.warnings
    assert readiness.WARNING_FINISHED_REMINDER_HOURS_INVALID in result.warnings


def test_evaluate_startup_readiness_splits_fatal_and_non_fatal():
    _set_valid_config()
    env.bot_token = ""
    runtime.customs_chat_id = 0

    startup = readiness.evaluate_startup_readiness()

    assert readiness.BLOCKER_BOT_TOKEN_MISSING in startup.fatal_blockers
    assert readiness.BLOCKER_CUSTOMS_CHAT_ID_MISSING in startup.non_fatal_blockers
    assert startup.can_start is False


def test_build_startup_config_error_contains_details_and_hints():
    startup = readiness.StartupReadiness(
        readiness=readiness.BriefEnvReadiness(),
        fatal_blockers=[readiness.BLOCKER_ANTHROPIC_API_KEY_MISSING],
        non_fatal_blockers=[],
    )

    err = readiness.build_startup_config_error(startup)

    rendered = err.render_terminal()
    assert err.exit_code == 2
    assert "ANTHROPIC_API_KEY" in rendered
    assert "How to fix" in rendered


def test_summarize_readiness_for_log_uses_singletons():
    _set_valid_config()
    data = readiness.summarize_readiness_for_log(readiness.evaluate_brief_env_readiness())

    assert data["ready"] is True
    assert data["bot_token_set"] is True
    assert data["anthropic_api_key_set"] is True
    assert data["customs_chat_id"] == -100500
