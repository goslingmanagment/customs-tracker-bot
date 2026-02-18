import pytest

from core.exceptions import InvalidTransitionError
from handlers.callback_actions import task_actions
from tests.fakes import FakeCallbackQuery, FakeTask, make_user


class _Session:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_action_take_success(monkeypatch):
    cb = FakeCallbackQuery(data="task:3:take", from_user=make_user(2, "model"))
    task = FakeTask(id=3, status="awaiting_confirmation", amount_total=120)
    session = _Session()

    calls = {"status": None, "feedback": None}

    async def _update(_session, _task, new_status, **_kwargs):
        calls["status"] = new_status

    async def _send_feedback_best_effort(_bot, _task, text, reply_markup=None, *, event):
        assert session.commits == 1
        calls["feedback"] = text
        return True

    monkeypatch.setattr(task_actions.task_repo, "update_task_status", _update)
    monkeypatch.setattr(task_actions, "refresh_card", lambda *_a, **_k: __import__("asyncio").sleep(0, result=True))
    monkeypatch.setattr(task_actions, "send_feedback_best_effort", _send_feedback_best_effort)

    await task_actions.action_take(cb, task, session, cb.from_user, "model", "@model")

    assert calls["status"] == "processing"
    assert cb.answers and "Взято" in cb.answers[0][0]
    assert "#003" in calls["feedback"]
    assert session.commits == 1


@pytest.mark.asyncio
async def test_action_take_invalid_transition(monkeypatch):
    cb = FakeCallbackQuery(data="task:3:take")
    task = FakeTask(id=3, status="draft")
    session = _Session()

    async def _update(*_args, **_kwargs):
        raise InvalidTransitionError("draft", "processing", [])

    monkeypatch.setattr(task_actions.task_repo, "update_task_status", _update)

    await task_actions.action_take(cb, task, session, cb.from_user, "u", "@u")

    assert cb.answers and "Переход недоступен" in cb.answers[0][0]


@pytest.mark.asyncio
async def test_action_deny_shot_handles_delete_failure(monkeypatch):
    cb = FakeCallbackQuery(data="task:3:deny_shot")
    task = FakeTask(id=3)

    monkeypatch.setattr(task_actions, "safe_delete_message", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))

    await task_actions.action_deny_shot(cb, task, object(), cb.from_user, "u", "@u")

    assert cb.answers and "Не удалось удалить" in cb.answers[0][0]


@pytest.mark.asyncio
async def test_action_open_sends_task_card(monkeypatch):
    cb = FakeCallbackQuery(data="task:8:open")
    task = FakeTask(id=8)

    feedback = []

    monkeypatch.setattr(task_actions, "get_card_for_status", lambda _task: ("card text", None))

    async def _send_feedback(_bot, _task, text, reply_markup=None):
        feedback.append((text, reply_markup))

    monkeypatch.setattr(task_actions, "send_feedback", _send_feedback)

    await task_actions.action_open(cb, task, object(), cb.from_user, "u", "@u")

    assert feedback and feedback[0][0] == "card text"
    assert cb.answers and "Открыт кастом #008" in cb.answers[0][0]
