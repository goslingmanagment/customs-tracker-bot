from types import SimpleNamespace

import pytest

from core.config import roles
from diagnostics import readiness
from handlers.commands import info


class _FakeLogger:
    def __init__(self):
        self.info_calls: list[tuple[str, dict]] = []

    def info(self, event: str, **kwargs):
        self.info_calls.append((event, kwargs))


class _FakeMessage:
    def __init__(self, user: SimpleNamespace | None):
        self.message_id = 123
        self.chat = SimpleNamespace(id=-1001)
        self.message_thread_id = 777
        self.from_user = user
        self.replies: list[tuple[str, dict]] = []

    async def reply(self, text: str, **kwargs):
        self.replies.append((text, kwargs))


@pytest.mark.asyncio
async def test_health_uses_human_readable_mappings_and_logs(monkeypatch):
    roles.admin_ids = []
    roles.admin_usernames = []

    monkeypatch.setattr(
        info,
        "evaluate_brief_env_readiness",
        lambda: readiness.BriefEnvReadiness(
            blockers=[readiness.BLOCKER_ANTHROPIC_API_KEY_MISSING],
            warnings=[readiness.WARNING_AI_CONFIDENCE_THRESHOLD_RANGE],
        ),
    )
    monkeypatch.setattr(
        info,
        "summarize_readiness_for_log",
        lambda _readiness: {
            "ready": False,
            "blockers": [readiness.BLOCKER_ANTHROPIC_API_KEY_MISSING],
            "warnings": [readiness.WARNING_AI_CONFIDENCE_THRESHOLD_RANGE],
            "blocker_count": 1,
            "warning_count": 1,
        },
    )

    fake_logger = _FakeLogger()
    monkeypatch.setattr(info, "logger", fake_logger)

    msg = _FakeMessage(SimpleNamespace(id=900, username="tester", full_name="Tester"))
    await info.cmd_health(msg)

    assert len(msg.replies) == 1
    text = msg.replies[0][0]
    assert "❌ Не готово" in text
    assert "Не задан ANTHROPIC_API_KEY." in text
    assert "AI_CONFIDENCE_THRESHOLD вне диапазона 0..1." in text
    assert readiness.BLOCKER_ANTHROPIC_API_KEY_MISSING not in text
    assert readiness.WARNING_AI_CONFIDENCE_THRESHOLD_RANGE not in text
    assert fake_logger.info_calls
    assert fake_logger.info_calls[0][0] == "health_check_requested"


@pytest.mark.asyncio
async def test_health_unknown_codes_fall_back_to_raw_values(monkeypatch):
    roles.admin_ids = []
    roles.admin_usernames = []

    monkeypatch.setattr(
        info,
        "evaluate_brief_env_readiness",
        lambda: readiness.BriefEnvReadiness(
            blockers=["my_custom_blocker"],
            warnings=["my_custom_warning"],
        ),
    )
    monkeypatch.setattr(
        info,
        "summarize_readiness_for_log",
        lambda _readiness: {
            "ready": False,
            "blockers": ["my_custom_blocker"],
            "warnings": ["my_custom_warning"],
            "blocker_count": 1,
            "warning_count": 1,
        },
    )

    msg = _FakeMessage(SimpleNamespace(id=901, username="tester2", full_name="Tester2"))
    await info.cmd_health(msg)

    assert len(msg.replies) == 1
    text = msg.replies[0][0]
    assert "my_custom_blocker" in text
    assert "my_custom_warning" in text
