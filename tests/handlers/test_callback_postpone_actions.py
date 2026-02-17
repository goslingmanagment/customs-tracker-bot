from types import SimpleNamespace

import pytest

from handlers.callback_actions import postpone_actions
from tests.fakes import FakeCallbackQuery, FakeMessage, FakeTask, make_user


def test_shift_deadline_uses_today_when_missing(monkeypatch):
    monkeypatch.setattr(postpone_actions, "today_local", lambda: "2026-02-18")
    iso_date, display = postpone_actions._shift_deadline(None, 3)
    assert iso_date == "2026-02-21"
    assert display == "21.02.2026"


@pytest.mark.asyncio
async def test_action_postpone_status_blocked(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:postpone")
    task = FakeTask(id=1, status="delivered")

    monkeypatch.setattr(postpone_actions, "postpone_status_error", lambda _s: "blocked")

    await postpone_actions.action_postpone(cb, task, object(), make_user(1), "u", "@u")

    assert cb.answers and cb.answers[0][0] == "blocked"


@pytest.mark.asyncio
async def test_action_postpone_sets_pending(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:postpone", from_user=make_user(10, "actor"))
    task = FakeTask(id=1, status="processing")

    captured = {}

    monkeypatch.setattr(postpone_actions, "postpone_status_error", lambda _s: None)
    monkeypatch.setattr(postpone_actions, "get_pending_postpone", lambda _uid: None)

    async def _send_feedback(_bot, _task, _text, reply_markup=None):
        return SimpleNamespace(message_id=901)

    def _set_pending(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(postpone_actions, "send_feedback", _send_feedback)
    monkeypatch.setattr(postpone_actions, "set_pending_postpone", _set_pending)

    await postpone_actions.action_postpone(cb, task, object(), cb.from_user, "actor", "@actor")

    assert captured["user_id"] == 10
    assert captured["task_id"] == 1
    assert captured["prompt_message_id"] == 901


@pytest.mark.asyncio
async def test_action_postpone_quick_inactive_session(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:postpone_1d", message=FakeMessage(text="x"))
    task = FakeTask(id=1, status="processing")

    monkeypatch.setattr(postpone_actions, "get_pending_postpone", lambda _uid: None)

    await postpone_actions._action_postpone_quick(cb, task, object(), make_user(1), "u", "@u", days=1)

    assert cb.answers and "неактивна" in cb.answers[0][0]


@pytest.mark.asyncio
async def test_action_postpone_quick_success(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:postpone_3d", from_user=make_user(1, "actor"))
    task = FakeTask(id=1, status="processing", deadline="2026-02-20")
    pending = SimpleNamespace(task_id=1)

    calls = {"updated": False, "cleared": False}

    monkeypatch.setattr(postpone_actions, "get_pending_postpone", lambda _uid: pending)
    monkeypatch.setattr(postpone_actions, "postpone_status_error", lambda _status: None)
    monkeypatch.setattr(postpone_actions, "refresh_card", lambda *_a, **_k: __import__("asyncio").sleep(0, result=True))
    monkeypatch.setattr(postpone_actions, "clear_pending_postpone_prompt_markup", lambda *_a, **_k: __import__("asyncio").sleep(0))
    monkeypatch.setattr(postpone_actions, "send_feedback", lambda *_a, **_k: __import__("asyncio").sleep(0))

    async def _update_deadline(_session, task_obj, new_deadline, **_kwargs):
        calls["updated"] = True
        task_obj.deadline = new_deadline

    def _clear(_uid):
        calls["cleared"] = True

    monkeypatch.setattr(postpone_actions.task_repo, "update_task_deadline", _update_deadline)
    monkeypatch.setattr(postpone_actions, "clear_pending_postpone", _clear)

    await postpone_actions._action_postpone_quick(cb, task, object(), cb.from_user, "actor", "@actor", days=3)

    assert calls["updated"] is True
    assert calls["cleared"] is True
    assert cb.answers and "+3 дн" in cb.answers[0][0]
