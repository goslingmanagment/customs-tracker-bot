from types import SimpleNamespace

import pytest

from core.config import runtime
from services import settings_service


@pytest.mark.asyncio
async def test_load_runtime_settings_forces_timezone_and_returns_dict(monkeypatch):
    row = SimpleNamespace(
        customs_chat_id=-100,
        customs_topic_id=777,
        ai_model="claude-x",
        ai_confidence_threshold=0.8,
        reminder_hours_before=12,
        overdue_reminder_cooldown_hours=3,
        high_urgency_cooldown_hours=1,
        finished_reminder_hours=8,
        timezone="Europe/Kyiv",
    )

    warnings: list[tuple[str, dict]] = []

    class _Logger:
        def warning(self, event, **kwargs):
            warnings.append((event, kwargs))

    async def _get_settings(_session):
        return row

    monkeypatch.setattr(settings_service.settings_repo, "get_app_settings", _get_settings)
    monkeypatch.setattr(settings_service, "logger", _Logger())

    result = await settings_service.load_runtime_settings(object())

    assert runtime.customs_chat_id == -100
    assert runtime.customs_topic_id == 777
    assert runtime.ai_model == "claude-x"
    assert runtime.ai_confidence_threshold == 0.8
    assert runtime.timezone == settings_service.RUNTIME_TIMEZONE
    assert result["timezone"] == settings_service.RUNTIME_TIMEZONE
    assert warnings and warnings[0][0] == "runtime_timezone_overridden"
