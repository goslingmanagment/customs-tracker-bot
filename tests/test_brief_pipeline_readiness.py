from types import SimpleNamespace

import pytest

from services import brief_pipeline


class _FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class _FakeMessage:
    def __init__(self, text: str):
        self.message_id = 101
        self.chat = SimpleNamespace(id=-1001)
        self.message_thread_id = 777
        self.from_user = SimpleNamespace(id=11, username="user11", full_name="User Eleven")
        self.text = text
        self.caption = None
        self.photo = []
        self.reply_to_message = None
        self.replies: list[tuple[str, object]] = []

    async def reply(self, text: str, reply_markup=None):
        self.replies.append((text, reply_markup))
        return SimpleNamespace(message_id=909)


class _FakeLogger:
    def __init__(self):
        self.warning_calls: list[tuple[str, dict]] = []

    def warning(self, event: str, **kwargs):
        self.warning_calls.append((event, kwargs))

    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


@pytest.mark.asyncio
async def test_process_brief_exits_when_env_not_ready(monkeypatch):
    session = _FakeSession()
    message = _FakeMessage("📦 описание заказа\nДлинный текст для теста")

    classify_called = {"value": False}
    mark_called = {"value": False}
    enqueue_called = {"value": False}

    monkeypatch.setattr(
        brief_pipeline,
        "evaluate_brief_env_readiness",
        lambda: SimpleNamespace(ready=False, blockers=["anthropic_api_key_missing"], warnings=[]),
    )
    monkeypatch.setattr(
        brief_pipeline,
        "summarize_readiness_for_log",
        lambda readiness: {
            "ready": readiness.ready,
            "blockers": readiness.blockers,
            "warnings": readiness.warnings,
        },
    )

    async def _classify_message(_text, _has_photo=False):
        classify_called["value"] = True
        return None

    async def _mark_processed(*_args, **_kwargs):
        mark_called["value"] = True

    async def _enqueue_retry(*_args, **_kwargs):
        enqueue_called["value"] = True

    monkeypatch.setattr(brief_pipeline, "classify_message", _classify_message)
    monkeypatch.setattr(brief_pipeline.message_repo, "mark_message_processed", _mark_processed)
    monkeypatch.setattr(brief_pipeline.retry_repo, "enqueue_ai_retry", _enqueue_retry)

    fake_logger = _FakeLogger()
    monkeypatch.setattr(brief_pipeline, "logger", fake_logger)

    await brief_pipeline.process_brief(message, session)

    assert classify_called["value"] is False
    assert mark_called["value"] is False
    assert enqueue_called["value"] is False
    assert fake_logger.warning_calls
    assert fake_logger.warning_calls[0][0] == "brief_pipeline_blocked_by_env"
    assert session.commits == 0


@pytest.mark.asyncio
async def test_process_brief_happy_path_still_creates_card(monkeypatch):
    session = _FakeSession()
    message = _FakeMessage("Любой длинный текст брифа")

    task = SimpleNamespace(
        id=55,
        amount_total=250.0,
        chat_id=message.chat.id,
        topic_id=message.message_thread_id,
    )
    classify_called = {"value": False}
    update_card_binding_called = {"value": False}
    processed_calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(
        brief_pipeline,
        "evaluate_brief_env_readiness",
        lambda: SimpleNamespace(ready=True, blockers=[], warnings=[]),
    )
    monkeypatch.setattr(
        brief_pipeline,
        "evaluate_message_for_processing",
        lambda _message: (True, "direct_marker", {"score": 3}),
    )

    async def _classify_message(_text, _has_photo=False):
        classify_called["value"] = True
        return {
            "is_task": True,
            "confidence": 0.92,
            "data": {"priority": "medium"},
        }

    async def _get_task_by_message(*_args, **_kwargs):
        return None

    async def _create_task(_session, **_kwargs):
        return task, True

    async def _update_task_bot_message_id(_session, _task, _message_id):
        update_card_binding_called["value"] = True

    async def _mark_processed(*args, **kwargs):
        processed_calls.append((args, kwargs))

    monkeypatch.setattr(brief_pipeline, "classify_message", _classify_message)
    monkeypatch.setattr(brief_pipeline.task_repo, "get_task_by_message", _get_task_by_message)
    monkeypatch.setattr(brief_pipeline.task_repo, "create_task", _create_task)
    monkeypatch.setattr(
        brief_pipeline.task_repo,
        "update_task_bot_message_id",
        _update_task_bot_message_id,
    )
    monkeypatch.setattr(brief_pipeline.message_repo, "mark_message_processed", _mark_processed)
    monkeypatch.setattr(brief_pipeline, "build_draft_card", lambda _task: ("card-text", None))

    await brief_pipeline.process_brief(message, session)

    assert classify_called["value"] is True
    assert message.replies == [("card-text", None)]
    assert update_card_binding_called["value"] is True
    assert len(processed_calls) == 1
    assert processed_calls[0][1].get("is_task") is True
    assert session.commits == 2
