from datetime import datetime, timezone
from types import SimpleNamespace

from core.config import runtime
from core import log_utils


def test_now_iso_is_valid_iso_datetime():
    value = log_utils.now_iso()
    parsed = datetime.fromisoformat(value)
    assert isinstance(parsed, datetime)


def test_today_local_uses_runtime_timezone(freeze_time):
    runtime.timezone = "UTC"
    freeze_time(log_utils, datetime(2026, 2, 17, 23, 0, tzinfo=timezone.utc))
    assert log_utils.today_local() == "2026-02-17"


def test_message_log_context_collects_payload():
    reply = SimpleNamespace(message_id=2)
    msg = SimpleNamespace(
        message_id=1,
        chat=SimpleNamespace(id=-100),
        message_thread_id=777,
        reply_to_message=reply,
        from_user=SimpleNamespace(id=44, username="tester"),
        text="hello",
        caption=None,
        photo=[1],
    )

    context = log_utils.message_log_context(msg)

    assert context["message_id"] == 1
    assert context["chat_id"] == -100
    assert context["topic_id"] == 777
    assert context["reply_to_message_id"] == 2
    assert context["from_user_id"] == 44
    assert context["from_username"] == "tester"
    assert context["has_text"] is True
    assert context["text_len"] == 5
    assert context["has_photo"] is True
