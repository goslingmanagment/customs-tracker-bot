from datetime import datetime

from pre_filter import evaluate_message_for_processing
from tests.fakes import FakeMessage, make_user


def test_prefilter_skips_no_text():
    msg = FakeMessage(text=None, caption=None)
    should, reason, details = evaluate_message_for_processing(msg)
    assert should is False
    assert reason == "no_text"
    assert details["text_len"] == 0


def test_prefilter_skips_forwarded_messages():
    msg = FakeMessage(text="длинный текст" * 5, forward_date=datetime.now())
    should, reason, _ = evaluate_message_for_processing(msg)
    assert should is False
    assert reason == "forwarded"


def test_prefilter_teamlead_bypass(monkeypatch):
    msg = FakeMessage(text="short", from_user=make_user(1, "lead"))
    monkeypatch.setattr("pre_filter.is_teamlead", lambda _user: True)

    should, reason, _ = evaluate_message_for_processing(msg)
    assert should is True
    assert reason == "teamlead_sender"


def test_prefilter_direct_marker_passes():
    msg = FakeMessage(text="📦 описание заказа\nкраткий текст" + "x" * 40)
    should, reason, details = evaluate_message_for_processing(msg)
    assert should is True
    assert reason == "direct_marker"
    assert details["has_direct_marker"] is True


def test_prefilter_heuristic_score_threshold():
    text = (
        "Это длинный текст с payment и дедлайн и ссылка https://fansly.com/test "
        "и 15 минут и еще слова для длины"
    )
    msg = FakeMessage(text=text)

    should, reason, details = evaluate_message_for_processing(msg)

    assert should is True
    assert reason == "heuristic_score"
    assert details["score"] >= 2


def test_prefilter_rejects_low_score():
    msg = FakeMessage(text="Привет как дела" + "x" * 30)
    should, reason, _ = evaluate_message_for_processing(msg)
    assert should is False
    assert reason == "heuristic_score_low"
