from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from services import postpone_service
from tests.fakes import FakeMessage, FakeTask, make_user


def test_postpone_status_error_matrix():
    assert postpone_service.postpone_status_error("awaiting_confirmation") is None
    assert postpone_service.postpone_status_error("processing") is None
    assert "ещё не подтверждён" in postpone_service.postpone_status_error("draft")
    assert postpone_service.postpone_status_error("delivered") == "Дедлайн нельзя менять в этом статусе"


def test_parse_deadline_input_supports_optional_year(freeze_time):
    freeze_time(postpone_service, datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc))

    iso_date, display = postpone_service._parse_deadline_input("05.03")
    assert iso_date == "2026-03-05"
    assert display == "05.03"

    iso_date2, display2 = postpone_service._parse_deadline_input("05.03.2027")
    assert iso_date2 == "2027-03-05"
    assert display2 == "05.03"


@pytest.mark.asyncio
async def test_process_deadline_change_text_rejects_forbidden(monkeypatch):
    message = FakeMessage(text="05.03", from_user=make_user(1, "user"))
    task = FakeTask(status="processing")

    monkeypatch.setattr(postpone_service, "can_change_deadline", lambda _u: False)

    result = await postpone_service.process_deadline_change_text(object(), message, task, text="05.03")

    assert result == "forbidden"
    assert message.replies
    assert "Только администраторы" in message.replies[0][0]


@pytest.mark.asyncio
async def test_process_deadline_change_text_handles_invalid_and_status_block(monkeypatch):
    message = FakeMessage(text="31.02", from_user=make_user(1, "lead"))
    task = FakeTask(status="draft")

    monkeypatch.setattr(postpone_service, "can_change_deadline", lambda _u: True)

    status_blocked = await postpone_service.process_deadline_change_text(
        object(),
        message,
        task,
        text="01.03",
    )
    assert status_blocked == "status_blocked"

    task.status = "processing"
    invalid = await postpone_service.process_deadline_change_text(
        object(),
        message,
        task,
        text="31.02",
    )
    assert invalid == "invalid_date"


@pytest.mark.asyncio
async def test_process_deadline_change_text_calls_apply(monkeypatch):
    message = FakeMessage(text="05.03", from_user=make_user(1, "lead"))
    task = FakeTask(status="processing")

    called = {}

    async def _apply(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(postpone_service, "can_change_deadline", lambda _u: True)
    monkeypatch.setattr(postpone_service, "_apply_deadline_change", _apply)

    result = await postpone_service.process_deadline_change_text(object(), message, task, text="05.03")

    assert result == "updated"
    assert called["new_deadline"].endswith("-03-05")
    assert called["display_deadline"] == "05.03"


@pytest.mark.asyncio
async def test_maybe_process_pending_postpone_mismatched_topic_returns_false(monkeypatch):
    postpone_service._PENDING_POSTPONES.clear()
    postpone_service.set_pending_postpone(
        user_id=1,
        task_id=10,
        chat_id=-100,
        topic_id=777,
        prompt_message_id=9000,
    )

    message = FakeMessage(text="05.03", chat_id=-100, topic_id=778, from_user=make_user(1, "u"))

    handled = await postpone_service.maybe_process_pending_postpone(message)
    assert handled is False
