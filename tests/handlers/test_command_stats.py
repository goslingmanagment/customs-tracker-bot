import pytest

from handlers.commands import stats
from tests.fakes import FakeMessage, FakeSessionFactory, make_user


class _Session:
    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_cmd_stats_denies_non_admin(monkeypatch):
    msg = FakeMessage(text="/stats", from_user=make_user(1, "user"))
    monkeypatch.setattr(stats, "is_admin", lambda _u: False)

    await stats.cmd_stats(msg)

    assert msg.replies and "только администраторам" in msg.replies[0][0].lower()


@pytest.mark.asyncio
async def test_cmd_stats_month_parsing(monkeypatch):
    session = _Session()
    msg = FakeMessage(text="/stats январь", from_user=make_user(1, "admin"))

    captured = {}

    async def _resolve(*_args, **_kwargs):
        return False

    async def _get_stats(_session, year, month):
        captured["year"] = year
        captured["month"] = month
        return {
            "total": 1,
            "completed": 1,
            "in_progress": 0,
            "finished": 0,
            "cancelled": 0,
            "total_amount": 100,
            "avg_amount": 100,
            "overdue": 0,
            "platforms": {"fansly": {"count": 1, "amount": 100}},
        }

    monkeypatch.setattr(stats, "is_admin", lambda _u: True)
    monkeypatch.setattr(stats, "async_session", FakeSessionFactory(session))
    monkeypatch.setattr(stats, "resolve_admin_identity", _resolve)
    monkeypatch.setattr(stats, "get_monthly_stats", _get_stats)

    await stats.cmd_stats(msg)

    assert captured["month"] == 1
    assert msg.replies and "Статистика" in msg.replies[0][0]
