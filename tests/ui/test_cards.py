from ui import cards
from tests.fakes import FakeTask


def test_build_draft_card_has_confirm_and_not_task_actions():
    task = FakeTask(id=12, status="draft", description="A" * 120)
    text, keyboard = cards.build_draft_card(task)

    assert "Кастом #012" in text
    callbacks = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert "task:12:confirm_brief" in callbacks
    assert "task:12:not_task" in callbacks


def test_get_card_for_status_fallback_to_draft():
    task = FakeTask(id=3, status="unknown")
    text, keyboard = cards.get_card_for_status(task)

    assert "Кастом #003" in text
    assert keyboard is not None
