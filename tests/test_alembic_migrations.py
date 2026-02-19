import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

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

    conn = sqlite3.connect(db_file)
    try:
        task_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(tasks)")
        }
    finally:
        conn.close()

    assert "description_original" in task_columns
    assert "outfit_original" in task_columns
    assert "notes_original" in task_columns


def _upgrade(db_file: Path, revision: str) -> None:
    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(project_root / "alembic"))
    env.db_path = str(db_file)
    command.upgrade(cfg, revision)


def test_alembic_backfills_original_brief_sections(tmp_path):
    db_file = tmp_path / "migration_backfill.sqlite3"
    _upgrade(db_file, "0002_add_ai_retry_queue")

    conn = sqlite3.connect(db_file)
    try:
        conn.execute(
            """
            INSERT INTO tasks (
                message_id, chat_id, topic_id, bot_message_id, sender_username,
                task_date, fan_link, fan_name, platform, amount_total, amount_paid, amount_remaining,
                payment_note, duration, description, outfit, notes, priority, deadline,
                status, finished_at, delivered_at, raw_text, ai_confidence, last_reminder_at,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                10,
                -100,
                777,
                None,
                "editor",
                "2026-02-18",
                None,
                "Brandon",
                "fansly",
                200.0,
                100.0,
                100.0,
                "sub + 100$",
                "8 minutes",
                "compact",
                "compact outfit",
                "compact notes",
                "high",
                "2026-02-24",
                "processing",
                None,
                None,
                (
                    "📦 Описание заказа\n"
                    "Дата: 18.02.2026\n"
                    "🎥 Описание задания:\n"
                    "Оригинальное длинное описание\n"
                    "👗 Одежда: аутфит из скрина\n"
                    "📝Заметки: без музыки\n"
                    "🔥Срочность: Высокая\n"
                ),
                0.92,
                None,
                "2026-02-18T10:00:00+00:00",
                "2026-02-18T10:00:00+00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    _upgrade(db_file, "head")

    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute(
            """
            SELECT description_original, outfit_original, notes_original
            FROM tasks
            WHERE message_id = 10
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "Оригинальное длинное описание"
    assert row[1] == "аутфит из скрина"
    assert row[2] == "без музыки"
