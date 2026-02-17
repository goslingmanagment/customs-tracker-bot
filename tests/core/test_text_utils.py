from types import SimpleNamespace

from core import text_utils


def test_esc_handles_none_and_html():
    assert text_utils.esc(None) == ""
    assert text_utils.esc("<b>hi</b>") == "&lt;b&gt;hi&lt;/b&gt;"


def test_normalize_username_variants():
    assert text_utils.normalize_username(" @TeStUser ") == "testuser"
    assert text_utils.normalize_username("   ") is None
    assert text_utils.normalize_username(None) is None


def test_compact_preview_compacts_and_truncates():
    assert text_utils.compact_preview("  a   b\n c  ", limit=20) == "a b c"
    assert text_utils.compact_preview("x" * 10, limit=5) == "xxxxx..."
    assert text_utils.compact_preview(None) is None


def test_user_display_name_prefers_username_then_full_name():
    assert text_utils.user_display_name(None) == "Пользователь"
    assert text_utils.user_display_name(SimpleNamespace(username="tester", full_name="T")) == "@tester"
    assert text_utils.user_display_name(SimpleNamespace(username=None, full_name="Tester Name")) == "Tester Name"
