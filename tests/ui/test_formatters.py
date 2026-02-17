from ui import formatters


def test_format_deadline_status_matrix(monkeypatch):
    monkeypatch.setattr(formatters, "today_local", lambda: "2026-02-18")

    assert "сегодня" in formatters.format_deadline_status("2026-02-18")
    assert "через 2" in formatters.format_deadline_status("2026-02-20")
    assert "просрочено" in formatters.format_deadline_status("2026-02-17")
    assert "до" in formatters.format_deadline_status("2026-02-25")
    assert formatters.format_deadline_status("bad").startswith("⏰")


def test_format_amount_and_days_overdue(monkeypatch):
    monkeypatch.setattr(formatters, "today_local", lambda: "2026-02-18")

    assert formatters.format_amount(None) == "—"
    assert "(x)" in formatters.format_amount(100, "x")
    assert formatters.format_days_overdue("2026-02-17") == "+1 день"
    assert formatters.format_days_overdue("2026-02-14") == "+4 дня"
    assert formatters.format_days_overdue("2026-02-10") == "+8 дней"
