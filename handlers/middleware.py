from typing import Any, Awaitable, Callable

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, Update

from core.text_utils import compact_preview

logger = structlog.get_logger()


class UpdateLogMiddleware(BaseMiddleware):
    """Debug middleware: logs every incoming Telegram update."""

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        message: Message | None = event.message or event.edited_message
        callback: CallbackQuery | None = event.callback_query

        callback_message = callback.message if callback else None
        callback_chat = getattr(callback_message, "chat", None)
        callback_thread_id = getattr(callback_message, "message_thread_id", None)
        replied_to = message.reply_to_message if message else None
        text = message.text or message.caption if message else None

        replied_text = replied_to.text or replied_to.caption if replied_to else None

        logger.info(
            "telegram_update_received",
            update_id=event.update_id,
            has_message=event.message is not None,
            has_edited_message=event.edited_message is not None,
            has_callback_query=event.callback_query is not None,
            message_id=message.message_id if message else None,
            callback_message_id=callback_message.message_id if callback_message else None,
            chat_id=(
                message.chat.id
                if message
                else (callback_chat.id if callback_chat else None)
            ),
            topic_id=(
                message.message_thread_id
                if message
                else callback_thread_id
            ),
            from_user_id=(
                message.from_user.id
                if message and message.from_user
                else (callback.from_user.id if callback and callback.from_user else None)
            ),
            from_username=(
                message.from_user.username
                if message and message.from_user
                else (callback.from_user.username if callback and callback.from_user else None)
            ),
            has_text=bool(text),
            text_len=len(text) if text else 0,
            starts_with_slash=bool(text and text.startswith("/")),
            is_reply=bool(message.reply_to_message) if message else False,
            has_photo=bool(message.photo) if message else False,
            text_preview=compact_preview(text),
            is_topic_message=bool(message.is_topic_message) if message else False,
            reply_to_message_id=replied_to.message_id if replied_to else None,
            reply_to_from_user_id=(
                replied_to.from_user.id if replied_to and replied_to.from_user else None
            ),
            reply_to_from_username=(
                replied_to.from_user.username if replied_to and replied_to.from_user else None
            ),
            reply_to_from_is_bot=(
                replied_to.from_user.is_bot if replied_to and replied_to.from_user else None
            ),
            reply_to_text_preview=compact_preview(replied_text),
        )
        return await handler(event, data)
