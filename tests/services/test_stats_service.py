import pytest

from db.models import Task
from services import stats_service


@pytest.mark.asyncio
async def test_get_monthly_stats_aggregates(db_session, monkeypatch):
    rows = [
        Task(
            message_id=1,
            chat_id=-100,
            topic_id=777,
            status="delivered",
            amount_total=100,
            platform="fansly",
            deadline="2026-02-10",
            created_at="2026-02-01T10:00:00+00:00",
            updated_at="2026-02-01T10:00:00+00:00",
        ),
        Task(
            message_id=2,
            chat_id=-100,
            topic_id=777,
            status="processing",
            amount_total=200,
            platform="onlyfans",
            deadline="2026-02-15",
            created_at="2026-02-02T10:00:00+00:00",
            updated_at="2026-02-02T10:00:00+00:00",
        ),
        Task(
            message_id=3,
            chat_id=-100,
            topic_id=777,
            status="finished",
            amount_total=50,
            platform=None,
            deadline="2026-02-12",
            created_at="2026-02-03T10:00:00+00:00",
            updated_at="2026-02-03T10:00:00+00:00",
        ),
        Task(
            message_id=4,
            chat_id=-100,
            topic_id=777,
            status="cancelled",
            amount_total=0,
            platform="fansly",
            deadline=None,
            created_at="2026-02-04T10:00:00+00:00",
            updated_at="2026-02-04T10:00:00+00:00",
        ),
        Task(
            message_id=5,
            chat_id=-100,
            topic_id=777,
            status="processing",
            amount_total=999,
            platform="fansly",
            deadline="2026-03-01",
            created_at="2026-03-01T10:00:00+00:00",
            updated_at="2026-03-01T10:00:00+00:00",
        ),
    ]
    db_session.add_all(rows)
    await db_session.flush()

    monkeypatch.setattr(stats_service, "today_local", lambda: "2026-02-20")

    stats = await stats_service.get_monthly_stats(db_session, 2026, 2)

    assert stats["total"] == 4
    assert stats["completed"] == 1
    assert stats["in_progress"] == 1
    assert stats["finished"] == 1
    assert stats["cancelled"] == 1
    assert stats["overdue"] == 2
    assert stats["total_amount"] == 350
    assert stats["avg_amount"] == 87.5
    assert stats["platforms"]["fansly"]["count"] == 2
    assert stats["platforms"]["unknown"]["count"] == 1
