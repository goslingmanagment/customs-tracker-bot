from types import SimpleNamespace

import pytest

import db.engine
from services import postpone_service


class _FakeBot:
    def __init__(self):
        self.reply_markup_edits: list[tuple[int, int, object | None]] = []

    async def edit_message_reply_markup(self, chat_id: int, message_id: int, reply_markup=None):
        self.reply_markup_edits.append((chat_id, message_id, reply_markup))


class _FakeMessage:
    def __init__(self, *, user_id: int, chat_id: int, topic_id: int | None, text: str, bot: _FakeBot):
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=chat_id)
        self.message_thread_id = topic_id
        self.text = text
        self.caption = None
        self.bot = bot
        self.replies: list[str] = []

    async def reply(self, text: str):
        self.replies.append(text)


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def _clear_pending_state():
    postpone_service._PENDING_POSTPONES.clear()
    yield
    postpone_service._PENDING_POSTPONES.clear()


@pytest.mark.asyncio
async def test_maybe_process_pending_postpone_clears_prompt_markup_after_success(monkeypatch):
    user_id = 42
    task_id = 11
    chat_id = -100500
    topic_id = 777
    prompt_message_id = 9001

    postpone_service.set_pending_postpone(
        user_id=user_id,
        task_id=task_id,
        chat_id=chat_id,
        topic_id=topic_id,
        prompt_message_id=prompt_message_id,
    )

    bot = _FakeBot()
    message = _FakeMessage(
        user_id=user_id,
        chat_id=chat_id,
        topic_id=topic_id,
        text="05.03",
        bot=bot,
    )

    async def _process_deadline_change_text(_session, _message, _task, _text):
        return "updated"

    async def _get_task_by_id(_session, lookup_id: int):
        if lookup_id == task_id:
            return SimpleNamespace(id=task_id)
        return None

    monkeypatch.setattr(
        postpone_service,
        "process_deadline_change_text",
        _process_deadline_change_text,
    )
    monkeypatch.setattr(postpone_service.task_repo, "get_task_by_id", _get_task_by_id)
    monkeypatch.setattr(db.engine, "async_session", lambda: _SessionContext())

    handled = await postpone_service.maybe_process_pending_postpone(message)

    assert handled is True
    assert postpone_service.get_pending_postpone(user_id) is None
    assert bot.reply_markup_edits == [(chat_id, prompt_message_id, None)]


@pytest.mark.asyncio
async def test_maybe_process_pending_postpone_clears_prompt_markup_after_timeout():
    user_id = 43
    chat_id = -100501
    topic_id = 778
    prompt_message_id = 9002

    postpone_service.set_pending_postpone(
        user_id=user_id,
        task_id=12,
        chat_id=chat_id,
        topic_id=topic_id,
        prompt_message_id=prompt_message_id,
    )
    postpone_service._PENDING_POSTPONES[user_id].expires_at = 0.0

    bot = _FakeBot()
    message = _FakeMessage(
        user_id=user_id,
        chat_id=chat_id,
        topic_id=topic_id,
        text="any text",
        bot=bot,
    )

    handled = await postpone_service.maybe_process_pending_postpone(message)

    assert handled is True
    assert message.replies == ["Время для ввода даты истекло. Нажмите ⏰ снова."]
    assert bot.reply_markup_edits == [(chat_id, prompt_message_id, None)]
