from services.task_service import build_task_kwargs, sanitize_ai_data


def test_sanitize_ai_data_normalizes_priority_and_deadline():
    data = {"priority": "urgent", "deadline": "31.02.2026"}
    out = sanitize_ai_data(data)

    assert out["priority"] == "medium"
    assert out["deadline"] is None


def test_sanitize_ai_data_keeps_valid_values():
    data = {"priority": "high", "deadline": "2026-02-20"}
    out = sanitize_ai_data(data)
    assert out["priority"] == "high"
    assert out["deadline"] == "2026-02-20"


def test_build_task_kwargs_maps_fields():
    data = {
        "task_date": "2026-02-17",
        "fan_link": "https://fansly.com/a",
        "fan_name": "A",
        "platform": "fansly",
        "amount_total": 100,
        "amount_paid": 50,
        "amount_remaining": 50,
        "payment_note": "half",
        "duration": "5 minutes",
        "description": "desc",
        "outfit": "dress",
        "notes": "note",
        "priority": "medium",
        "deadline": "2026-02-20",
    }
    raw_text = (
        "Описание задания:\n"
        "Оригинальное описание.\n"
        "Одежда: красное платье\n"
        "Заметки: без музыки\n"
    )

    kwargs = build_task_kwargs(
        data,
        message_id=1,
        chat_id=-100,
        topic_id=777,
        raw_text=raw_text,
        ai_confidence=0.9,
        sender_username="user",
    )

    assert kwargs["message_id"] == 1
    assert kwargs["chat_id"] == -100
    assert kwargs["topic_id"] == 777
    assert kwargs["raw_text"] == raw_text
    assert kwargs["ai_confidence"] == 0.9
    assert kwargs["sender_username"] == "user"
    assert kwargs["payment_note"] == "half"
    assert kwargs["description_original"] == "Оригинальное описание."
    assert kwargs["outfit_original"] == "красное платье"
    assert kwargs["notes_original"] == "без музыки"
