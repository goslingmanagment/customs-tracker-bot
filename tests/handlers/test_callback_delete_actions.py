import pytest

from handlers.callback_actions import delete_actions
from tests.fakes import FakeCallbackQuery, FakeMessage, FakeTask, make_user


@pytest.mark.asyncio
async def test_action_not_task_rejects_non_draft():
    cb = FakeCallbackQuery(data="task:1:not_task")
    task = FakeTask(id=1, status="processing")

    await delete_actions.action_not_task(cb, task, object(), make_user(1), "u", "@u")

    assert cb.answers and "только для черновика" in cb.answers[0][0]


@pytest.mark.asyncio
async def test_action_not_task_confirm_expired(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:not_task_confirm", message=FakeMessage(text="x"))
    task = FakeTask(id=1, status="draft")

    monkeypatch.setattr(delete_actions, "consume_delete_confirmation", lambda *_a, **_k: False)
    monkeypatch.setattr(delete_actions, "refresh_card", lambda *_a, **_k: __import__("asyncio").sleep(0, result=True))

    await delete_actions.action_not_task_confirm(cb, task, object(), make_user(1), "u", "@u")

    assert cb.answers and "Подтверждение истекло" in cb.answers[0][0]


@pytest.mark.asyncio
async def test_action_not_task_confirm_success(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:not_task_confirm", message=FakeMessage(text="x"))
    task = FakeTask(id=1, status="draft")

    deleted = {"value": False}

    monkeypatch.setattr(delete_actions, "consume_delete_confirmation", lambda *_a, **_k: True)
    monkeypatch.setattr(delete_actions, "send_feedback", lambda *_a, **_k: __import__("asyncio").sleep(0))
    monkeypatch.setattr(
        delete_actions.task_repo,
        "delete_task",
        lambda *_a, **_k: __import__("asyncio").sleep(0),
    )

    async def _safe_delete(*_args, **_kwargs):
        deleted["value"] = True
        return True

    monkeypatch.setattr(delete_actions, "safe_delete_message", _safe_delete)

    await delete_actions.action_not_task_confirm(cb, task, object(), make_user(1), "u", "@u")

    assert deleted["value"] is True
    assert cb.answers and cb.answers[0][0] == "Удалено"


@pytest.mark.asyncio
async def test_action_not_task_cancel_sends_feedback_when_refresh_failed(monkeypatch):
    cb = FakeCallbackQuery(data="task:1:not_task_cancel")
    task = FakeTask(id=1, status="draft")

    called = {"feedback": False}

    monkeypatch.setattr(delete_actions, "clear_delete_confirmation", lambda *_a, **_k: None)
    monkeypatch.setattr(delete_actions, "refresh_card", lambda *_a, **_k: __import__("asyncio").sleep(0, result=False))

    async def _feedback(*_args, **_kwargs):
        called["feedback"] = True

    monkeypatch.setattr(delete_actions, "send_feedback", _feedback)

    await delete_actions.action_not_task_cancel(cb, task, object(), make_user(1), "u", "@u")

    assert called["feedback"] is True
    assert cb.answers and "Удаление отменено" in cb.answers[0][0]
