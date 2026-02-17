from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


def make_user(
    user_id: int = 1,
    username: str | None = "user",
    full_name: str = "User",
    *,
    is_bot: bool = False,
):
    return SimpleNamespace(
        id=user_id,
        username=username,
        full_name=full_name,
        is_bot=is_bot,
    )


class FakeBot:
    def __init__(self):
        self.sent_messages: list[dict[str, Any]] = []
        self.edited_texts: list[dict[str, Any]] = []
        self.edited_reply_markups: list[dict[str, Any]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs):
        payload = {"chat_id": chat_id, "text": text, **kwargs}
        self.sent_messages.append(payload)
        message_id = kwargs.get("reply_to_message_id", 1000) + len(self.sent_messages)
        return SimpleNamespace(
            message_id=message_id,
            chat=SimpleNamespace(id=chat_id),
            message_thread_id=kwargs.get("message_thread_id"),
            from_user=make_user(999, "bot", "Bot", is_bot=True),
            text=text,
            caption=None,
            reply_to_message=None,
        )

    async def edit_message_text(self, text: str, chat_id: int, message_id: int, **kwargs):
        self.edited_texts.append(
            {
                "text": text,
                "chat_id": chat_id,
                "message_id": message_id,
                **kwargs,
            }
        )

    async def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup=None,
    ):
        self.edited_reply_markups.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": reply_markup,
            }
        )


class FakeMessage:
    def __init__(
        self,
        *,
        text: str | None = None,
        caption: str | None = None,
        chat_id: int = -1001,
        topic_id: int | None = 777,
        message_id: int = 101,
        from_user=None,
        reply_to_message=None,
        bot: FakeBot | None = None,
        chat_type: str = "supergroup",
        is_topic_message: bool = True,
        photo=None,
        forward_date=None,
    ):
        self.text = text
        self.caption = caption
        self.chat = SimpleNamespace(id=chat_id, type=chat_type)
        self.message_thread_id = topic_id
        self.message_id = message_id
        self.from_user = from_user if from_user is not None else make_user()
        self.reply_to_message = reply_to_message
        self.bot = bot or FakeBot()
        self.is_topic_message = is_topic_message
        self.photo = photo if photo is not None else []
        self.forward_date = forward_date

        self.replies: list[tuple[str, dict[str, Any]]] = []
        self.answers: list[tuple[str, dict[str, Any]]] = []
        self.deleted = False

    async def reply(self, text: str, **kwargs):
        self.replies.append((text, kwargs))
        return SimpleNamespace(
            message_id=2000 + len(self.replies),
            chat=self.chat,
            message_thread_id=self.message_thread_id,
            from_user=make_user(999, "bot", "Bot", is_bot=True),
            text=text,
            caption=None,
            reply_to_message=self,
        )

    async def answer(self, text: str, **kwargs):
        self.answers.append((text, kwargs))
        return await self.reply(text, **kwargs)

    async def delete(self):
        self.deleted = True


class FakeCallbackQuery:
    def __init__(
        self,
        *,
        data: str,
        from_user=None,
        message: FakeMessage | None = None,
        bot: FakeBot | None = None,
    ):
        self.data = data
        self.from_user = from_user if from_user is not None else make_user()
        self.message = message
        self.bot = bot or (message.bot if message is not None else FakeBot())
        self.answers: list[tuple[str | None, dict[str, Any]]] = []

    async def answer(self, text: str | None = None, **kwargs):
        self.answers.append((text, kwargs))


class FakeSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return FakeSessionContext(self._session)


@dataclass
class FakeTask:
    id: int = 1
    status: str = "draft"
    amount_total: float | None = 100.0
    deadline: str | None = None
    priority: str = "medium"
    description: str | None = "desc"
    duration: str | None = None
    payment_note: str | None = None
    fan_name: str | None = None
    fan_link: str | None = None
    platform: str | None = None
    chat_id: int = -1001
    topic_id: int | None = 777
    bot_message_id: int | None = 555
    message_id: int = 101
    finished_at: str | None = None
    delivered_at: str | None = None
    last_reminder_at: str | None = None
    task_date: str | None = None
    raw_text: str | None = None
    amount_paid: float | None = None
    amount_remaining: float | None = None
    outfit: str | None = None
    notes: str | None = None
