import sqlite3

import pytest

from core.config import env
from db import engine as db_engine


@pytest.mark.asyncio
async def test_alembic_upgrade_creates_expected_tables_and_indexes(tmp_path):
    db_file = tmp_path / "migrations.sqlite3"
    env.db_path = str(db_file)

    await db_engine.init_db()

    conn = sqlite3.connect(db_file)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
    finally:
        conn.close()

    assert "tasks" in tables
    assert "status_logs" in tables
    assert "app_settings" in tables
    assert "ai_retry_queue" in tables

    assert "ix_tasks_status" in indexes
    assert "ix_tasks_deadline" in indexes
    assert "uq_ai_retry_queue_chat_message" in indexes
