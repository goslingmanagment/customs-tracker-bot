from types import SimpleNamespace

from core.config import runtime
from handlers import filters


def _msg(chat_id: int, topic_id: int | None, reply_to_message_id: int | None = None):
    reply = None
    if reply_to_message_id is not None:
        reply = SimpleNamespace(message_id=reply_to_message_id)
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        message_thread_id=topic_id,
        reply_to_message=reply,
    )


def test_is_in_working_topic_and_chat():
    runtime.customs_chat_id = -100
    runtime.customs_topic_id = 777

    assert filters.is_in_working_topic(_msg(-100, 777)) is True
    assert filters.is_in_working_topic(_msg(-100, 778)) is False
    assert filters.is_in_working_chat(_msg(-100, 123)) is True
    assert filters.is_in_working_chat(_msg(-101, 777)) is False


def test_topic_root_reply_detection():
    msg = _msg(-100, 777, reply_to_message_id=777)
    assert filters.is_topic_root_reply(msg) is True

    not_root = _msg(-100, 777, reply_to_message_id=500)
    assert filters.is_topic_root_reply(not_root) is False
