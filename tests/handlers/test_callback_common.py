from datetime import datetime, timezone

import pytest

from handlers.callback_actions import common
from tests.fakes import FakeCallbackQuery, FakeMessage, FakeTask, make_user


def test_parse_callback_and_denied_messages():
    assert common.parse_callback("task:12:take") == (12, "take")
    assert common.parse_callback("bad") is None

    assert "модели" in common.denied_message("take")
    assert "администраторам" in common.denied_message("confirm_brief")
    assert "администраторам" in common.denied_message("postpone")


def test_format_deadline_for_prompt_and_card_refresh_note():
    assert common.format_deadline_for_prompt("2026-02-20") == "20.02.2026"
    assert common.format_deadline_for_prompt("bad") == "bad"
    assert "Откройте /task 5" in common.card_refresh_note(5)


def test_delete_confirmation_ttl_lifecycle(monkeypatch):
    common._PENDING_DELETE_CONFIRMATIONS.clear()

    t0 = datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(common.time, "time", lambda: t0)

    common.set_delete_confirmation(1, 9)
    assert common.consume_delete_confirmation(1, 9) is True
    assert common.consume_delete_confirmation(1, 9) is False

    common.set_delete_confirmation(1, 9)
    monkeypatch.setattr(common.time, "time", lambda: t0 + common.DELETE_CONFIRM_TTL_SECONDS + 1)
    assert common.consume_delete_confirmation(1, 9) is False


@pytest.mark.asyncio
async def test_refresh_card_updates_quick_open_and_canonical_cards(monkeypatch):
    cb_message = FakeMessage(message_id=321)
    cb = FakeCallbackQuery(
        data="task:1:open",
        from_user=make_user(),
        message=cb_message,
    )
    task = FakeTask(id=1, bot_message_id=700)

    monkeypatch.setattr(common, "get_card_for_status", lambda _task: ("card", None))

    ok = await common.refresh_card(cb, task)
    assert ok is True
    assert [item["message_id"] for item in cb.bot.edited_texts] == [321, 700]


@pytest.mark.asyncio
async def test_refresh_card_updates_only_once_for_same_message_id(monkeypatch):
    cb_message = FakeMessage(message_id=700)
    cb = FakeCallbackQuery(
        data="task:1:open",
        from_user=make_user(),
        message=cb_message,
    )
    task = FakeTask(id=1, bot_message_id=700)

    monkeypatch.setattr(common, "get_card_for_status", lambda _task: ("card", None))

    ok = await common.refresh_card(cb, task)
    assert ok is True
    assert [item["message_id"] for item in cb.bot.edited_texts] == [700]


@pytest.mark.asyncio
async def test_refresh_card_fallbacks_to_canonical_when_no_callback_message(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:open", from_user=make_user())
    task = FakeTask(id=1, bot_message_id=700)

    monkeypatch.setattr(common, "get_card_for_status", lambda _task: ("card", None))

    ok = await common.refresh_card(cb, task)
    assert ok is True
    assert [item["message_id"] for item in cb.bot.edited_texts] == [700]


@pytest.mark.asyncio
async def test_refresh_card_treats_not_modified_as_success(monkeypatch):
    cb_message = FakeMessage(message_id=700)
    cb = FakeCallbackQuery(
        data="task:1:open",
        from_user=make_user(),
        message=cb_message,
    )
    task = FakeTask(id=1, bot_message_id=700)

    monkeypatch.setattr(common, "get_card_for_status", lambda _task: ("card", None))

    async def _not_modified(*_args, **_kwargs):
        raise RuntimeError("Bad Request: message is not modified")

    monkeypatch.setattr(cb.bot, "edit_message_text", _not_modified)
    ok = await common.refresh_card(cb, task)
    assert ok is True


@pytest.mark.asyncio
async def test_refresh_card_returns_false_on_edit_errors(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:open", from_user=make_user())
    task = FakeTask(id=1, bot_message_id=700)

    monkeypatch.setattr(common, "get_card_for_status", lambda _task: ("card", None))

    async def _fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cb.bot, "edit_message_text", _fail)
    failed = await common.refresh_card(cb, task)
    assert failed is False
