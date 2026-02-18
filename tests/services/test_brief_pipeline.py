from types import SimpleNamespace

import pytest

from core.exceptions import AITransientError
from services import brief_pipeline
from tests.fakes import FakeMessage, FakeTask


class _Session:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_prefilter_reject_marks_processed(monkeypatch):
    session = _Session()
    message = FakeMessage(text="hello")

    marked = {"value": False}

    monkeypatch.setattr(brief_pipeline, "evaluate_brief_env_readiness", lambda: SimpleNamespace(ready=True, blockers=[], warnings=[]))
    monkeypatch.setattr(brief_pipeline, "evaluate_message_for_processing", lambda _m: (False, "too_short", {}))

    async def _mark(*_args, **_kwargs):
        marked["value"] = True

    monkeypatch.setattr(brief_pipeline.message_repo, "mark_message_processed", _mark)

    await brief_pipeline.process_brief(message, session)

    assert marked["value"] is True
    assert session.commits == 1


@pytest.mark.asyncio
async def test_transient_ai_failure_enqueues_retry(monkeypatch):
    session = _Session()
    message = FakeMessage(text="long text" * 20)

    enqueue_called = {"value": False}

    monkeypatch.setattr(brief_pipeline, "evaluate_brief_env_readiness", lambda: SimpleNamespace(ready=True, blockers=[], warnings=[]))
    monkeypatch.setattr(brief_pipeline, "evaluate_message_for_processing", lambda _m: (True, "direct", {}))

    async def _classify(*_args, **_kwargs):
        raise AITransientError("x")

    async def _enqueue(*_args, **_kwargs):
        enqueue_called["value"] = True

    monkeypatch.setattr(brief_pipeline, "classify_message", _classify)
    monkeypatch.setattr(brief_pipeline.retry_repo, "enqueue_ai_retry", _enqueue)

    await brief_pipeline.process_brief(message, session)

    assert enqueue_called["value"] is True
    assert session.commits == 1


@pytest.mark.asyncio
async def test_ai_none_logs_failure_and_notifies_admins(monkeypatch):
    session = _Session()
    message = FakeMessage(text="long text" * 20)

    parse_failure = {"value": False}
    marked = {"value": False}
    notified = {"value": False}

    monkeypatch.setattr(brief_pipeline, "evaluate_brief_env_readiness", lambda: SimpleNamespace(ready=True, blockers=[], warnings=[]))
    monkeypatch.setattr(brief_pipeline, "evaluate_message_for_processing", lambda _m: (True, "direct", {}))

    async def _classify(*_args, **_kwargs):
        return None

    async def _log_pf(*_args, **_kwargs):
        parse_failure["value"] = True

    async def _mark(*_args, **_kwargs):
        marked["value"] = True

    async def _notify(*_args, **_kwargs):
        notified["value"] = True

    monkeypatch.setattr(brief_pipeline, "classify_message", _classify)
    monkeypatch.setattr(brief_pipeline.message_repo, "log_parse_failure", _log_pf)
    monkeypatch.setattr(brief_pipeline.message_repo, "mark_message_processed", _mark)
    monkeypatch.setattr(brief_pipeline, "_notify_admins_about_ai_failure", _notify)

    await brief_pipeline.process_brief(message, session)

    assert parse_failure["value"] is True
    assert marked["value"] is True
    assert notified["value"] is True
    assert session.commits == 1


@pytest.mark.asyncio
async def test_low_confidence_is_marked_not_task(monkeypatch):
    session = _Session()
    message = FakeMessage(text="long text" * 20)

    marked = []

    monkeypatch.setattr(brief_pipeline, "evaluate_brief_env_readiness", lambda: SimpleNamespace(ready=True, blockers=[], warnings=[]))
    monkeypatch.setattr(brief_pipeline, "evaluate_message_for_processing", lambda _m: (True, "direct", {}))
    async def _classify(*_args, **_kwargs):
        return {"is_task": True, "confidence": 0.2, "data": {}}

    monkeypatch.setattr(brief_pipeline, "classify_message", _classify)

    async def _mark(*_args, **kwargs):
        marked.append(kwargs)

    monkeypatch.setattr(brief_pipeline.message_repo, "mark_message_processed", _mark)

    await brief_pipeline.process_brief(message, session)

    assert len(marked) == 1
    assert marked[0].get("is_task", False) is False


@pytest.mark.asyncio
async def test_existing_task_shortcuts_processing(monkeypatch):
    session = _Session()
    message = FakeMessage(text="long text" * 20)

    monkeypatch.setattr(brief_pipeline, "evaluate_brief_env_readiness", lambda: SimpleNamespace(ready=True, blockers=[], warnings=[]))
    monkeypatch.setattr(brief_pipeline, "evaluate_message_for_processing", lambda _m: (True, "direct", {}))
    async def _classify(*_args, **_kwargs):
        return {"is_task": True, "confidence": 0.9, "data": {}}

    async def _get_existing(*_args, **_kwargs):
        return FakeTask(id=88)

    monkeypatch.setattr(brief_pipeline, "classify_message", _classify)
    monkeypatch.setattr(brief_pipeline.task_repo, "get_task_by_message", _get_existing)

    marked = []

    async def _mark(*_args, **kwargs):
        marked.append(kwargs)

    monkeypatch.setattr(brief_pipeline.message_repo, "mark_message_processed", _mark)

    await brief_pipeline.process_brief(message, session)

    assert marked and marked[0].get("is_task") is True


@pytest.mark.asyncio
async def test_create_race_and_card_send_failure_paths(monkeypatch):
    session = _Session()
    message = FakeMessage(text="long text" * 20)

    monkeypatch.setattr(brief_pipeline, "evaluate_brief_env_readiness", lambda: SimpleNamespace(ready=True, blockers=[], warnings=[]))
    monkeypatch.setattr(brief_pipeline, "evaluate_message_for_processing", lambda _m: (True, "direct", {}))
    async def _classify(*_args, **_kwargs):
        return {"is_task": True, "confidence": 0.9, "data": {}}

    async def _get_missing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(brief_pipeline, "classify_message", _classify)
    monkeypatch.setattr(brief_pipeline.task_repo, "get_task_by_message", _get_missing)

    async def _create_race(_session, **_kwargs):
        return FakeTask(id=9), False

    monkeypatch.setattr(brief_pipeline.task_repo, "create_task", _create_race)

    marked = []

    async def _mark(*_args, **kwargs):
        marked.append(kwargs)

    monkeypatch.setattr(brief_pipeline.message_repo, "mark_message_processed", _mark)

    await brief_pipeline.process_brief(message, session)
    assert marked and marked[0].get("is_task") is True

    async def _create_ok(_session, **_kwargs):
        return FakeTask(id=10), True

    async def _reply_fail(*_args, **_kwargs):
        raise RuntimeError("send fail")

    notified = {"value": False}

    async def _notify_ops(*_args, **_kwargs):
        notified["value"] = True

    monkeypatch.setattr(brief_pipeline.task_repo, "create_task", _create_ok)
    monkeypatch.setattr(message, "reply", _reply_fail)
    monkeypatch.setattr(brief_pipeline, "_notify_admins_about_operational_issue", _notify_ops)

    await brief_pipeline.process_brief(message, session)
    assert notified["value"] is True
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_create_task_failure_logs_parse_failure_and_notifies_admins(monkeypatch):
    session = _Session()
    message = FakeMessage(text="long text" * 20)

    flags = {"parse_failure": False, "notified": False}

    monkeypatch.setattr(
        brief_pipeline,
        "evaluate_brief_env_readiness",
        lambda: SimpleNamespace(ready=True, blockers=[], warnings=[]),
    )
    monkeypatch.setattr(
        brief_pipeline, "evaluate_message_for_processing", lambda _m: (True, "direct", {})
    )
    monkeypatch.setattr(
        brief_pipeline,
        "classify_message",
        lambda *_a, **_k: __import__("asyncio").sleep(
            0, result={"is_task": True, "confidence": 0.9, "data": {}}
        ),
    )
    monkeypatch.setattr(
        brief_pipeline.task_repo,
        "get_task_by_message",
        lambda *_a, **_k: __import__("asyncio").sleep(0, result=None),
    )

    async def _create_fail(*_args, **_kwargs):
        raise RuntimeError("db down")

    async def _log_parse_failure(*_args, **_kwargs):
        flags["parse_failure"] = True

    async def _notify_ops(*_args, **_kwargs):
        flags["notified"] = True

    monkeypatch.setattr(brief_pipeline.task_repo, "create_task", _create_fail)
    monkeypatch.setattr(brief_pipeline.message_repo, "log_parse_failure", _log_parse_failure)
    monkeypatch.setattr(brief_pipeline, "_notify_admins_about_operational_issue", _notify_ops)

    await brief_pipeline.process_brief(message, session)

    assert session.rollbacks >= 1
    assert session.commits >= 1
    assert flags["parse_failure"] is True
    assert flags["notified"] is True
