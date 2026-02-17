from aiogram.filters import Filter
from aiogram.types import Message

from core.config import runtime


def is_in_working_topic(message: Message) -> bool:
    chat_id = runtime.customs_chat_id
    topic_id = runtime.customs_topic_id
    if chat_id == 0 or topic_id == 0:
        return False
    return message.chat.id == chat_id and message.message_thread_id == topic_id


def is_in_working_chat(message: Message) -> bool:
    chat_id = runtime.customs_chat_id
    if chat_id == 0:
        return False
    return message.chat.id == chat_id


class WorkingTopicFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return is_in_working_topic(message)


class WorkingChatFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return is_in_working_chat(message)


def is_topic_root_reply(message: Message) -> bool:
    """In Telegram forums every message is a 'reply' to the topic root.

    Detect this so we can treat such messages as normal (not real replies).
    """
    replied = message.reply_to_message
    if not replied:
        return False
    return (
        message.message_thread_id is not None
        and replied.message_id == message.message_thread_id
    )
