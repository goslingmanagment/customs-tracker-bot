import asyncio
from types import SimpleNamespace

import pytest

from ai import classifier
from core.exceptions import AITransientError


def test_normalize_classifier_result_valid_task_payload():
    payload = {
        "is_task": True,
        "confidence": 0.92,
        "data": {
            "task_date": "2026-02-17",
            "deadline": "bad-date",
            "priority": "urgent",
            "platform": "Fansly",
            "fan_name": " User ",
            "amount_total": "100.5",
            "amount_paid": 50,
            "amount_remaining": None,
        },
    }

    result = classifier._normalize_classifier_result(payload)

    assert result is not None
    assert result["is_task"] is True
    assert result["confidence"] == 0.92
    assert result["data"]["platform"] == "fansly"
    assert result["data"]["priority"] == "medium"
    assert result["data"]["deadline"] is None
    assert result["data"]["amount_total"] == 100.5


def test_normalize_classifier_result_rejects_invalid_schema():
    assert classifier._normalize_classifier_result("nope") is None
    assert classifier._normalize_classifier_result({"is_task": "yes"}) is None
    assert classifier._normalize_classifier_result({"is_task": False, "confidence": 1.5}) is None


@pytest.mark.asyncio
async def test_classify_message_strips_markdown_json(monkeypatch):
    async def _create(**_kwargs):
        return SimpleNamespace(
            content=[
                SimpleNamespace(
                    text='```json\n{"is_task": false, "confidence": 0.9, "reason": "chat"}\n```'
                )
            ]
        )

    monkeypatch.setattr(
        classifier,
        "client",
        SimpleNamespace(messages=SimpleNamespace(create=_create)),
    )

    result = await classifier.classify_message("text", has_photo=False)
    assert result == {"is_task": False, "confidence": 0.9, "reason": "chat"}


@pytest.mark.asyncio
async def test_classify_message_returns_none_on_bad_json(monkeypatch):
    async def _create(**_kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text="{not-json")])

    monkeypatch.setattr(
        classifier,
        "client",
        SimpleNamespace(messages=SimpleNamespace(create=_create)),
    )

    result = await classifier.classify_message("text")
    assert result is None


@pytest.mark.asyncio
async def test_classify_message_raises_after_transient_retries(monkeypatch):
    async def _create(**_kwargs):
        raise asyncio.TimeoutError("timeout")

    async def _sleep(_seconds):
        return None

    monkeypatch.setattr(
        classifier,
        "client",
        SimpleNamespace(messages=SimpleNamespace(create=_create)),
    )
    monkeypatch.setattr(classifier, "AI_MAX_INLINE_RETRIES", 1)
    monkeypatch.setattr(classifier, "AI_RETRY_BASE_DELAY", 0)
    monkeypatch.setattr(classifier.asyncio, "sleep", _sleep)

    with pytest.raises(AITransientError):
        await classifier.classify_message("text")
