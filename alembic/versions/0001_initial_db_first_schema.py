"""initial db-first schema

Revision ID: 0001_initial_db_first
Revises:
Create Date: 2026-02-16 01:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_db_first"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customs_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("customs_topic_id", sa.BigInteger(), nullable=False),
        sa.Column("ai_model", sa.String(length=128), nullable=False),
        sa.Column("ai_confidence_threshold", sa.Float(), nullable=False),
        sa.Column("reminder_hours_before", sa.Integer(), nullable=False),
        sa.Column("overdue_reminder_cooldown_hours", sa.Integer(), nullable=False),
        sa.Column("high_urgency_cooldown_hours", sa.Integer(), nullable=False),
        sa.Column("finished_reminder_hours", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.Column("updated_at", sa.String(length=30), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_app_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "parse_failures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("error_type", sa.String(length=50), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "processed_messages",
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("is_task", sa.Boolean(), nullable=False),
        sa.Column("processed_at", sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint("message_id", "chat_id"),
    )

    op.create_table(
        "role_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.Column("updated_at", sa.String(length=30), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_name", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_role_memberships_role",
        "role_memberships",
        ["role"],
        unique=False,
    )
    op.create_index(
        "uq_role_memberships_role_user_id",
        "role_memberships",
        ["role", "user_id"],
        unique=True,
    )
    op.create_index(
        "uq_role_memberships_role_username",
        "role_memberships",
        ["role", "username"],
        unique=True,
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("bot_message_id", sa.BigInteger(), nullable=True),
        sa.Column("sender_username", sa.String(length=100), nullable=True),
        sa.Column("task_date", sa.String(length=20), nullable=True),
        sa.Column("fan_link", sa.String(length=500), nullable=True),
        sa.Column("fan_name", sa.String(length=200), nullable=True),
        sa.Column("platform", sa.String(length=20), nullable=True),
        sa.Column("amount_total", sa.Float(), nullable=True),
        sa.Column("amount_paid", sa.Float(), nullable=True),
        sa.Column("amount_remaining", sa.Float(), nullable=True),
        sa.Column("payment_note", sa.Text(), nullable=True),
        sa.Column("duration", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("outfit", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("deadline", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("finished_at", sa.String(length=30), nullable=True),
        sa.Column("delivered_at", sa.String(length=30), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("last_reminder_at", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.Column("updated_at", sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tasks_chat_message", "tasks", ["chat_id", "message_id"], unique=True)
    op.create_index("ix_tasks_deadline", "tasks", ["deadline"], unique=False)
    op.create_index("ix_tasks_status", "tasks", ["status"], unique=False)

    op.create_table(
        "status_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("changed_by_id", sa.BigInteger(), nullable=True),
        sa.Column("changed_by_name", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.bulk_insert(
        sa.table(
            "app_settings",
            sa.column("id", sa.Integer()),
            sa.column("customs_chat_id", sa.BigInteger()),
            sa.column("customs_topic_id", sa.BigInteger()),
            sa.column("ai_model", sa.String()),
            sa.column("ai_confidence_threshold", sa.Float()),
            sa.column("reminder_hours_before", sa.Integer()),
            sa.column("overdue_reminder_cooldown_hours", sa.Integer()),
            sa.column("high_urgency_cooldown_hours", sa.Integer()),
            sa.column("finished_reminder_hours", sa.Integer()),
            sa.column("timezone", sa.String()),
            sa.column("created_at", sa.String()),
            sa.column("updated_at", sa.String()),
        ),
        [
            {
                "id": 1,
                "customs_chat_id": 0,
                "customs_topic_id": 0,
                "ai_model": "claude-sonnet-4-5-20250929",
                "ai_confidence_threshold": 0.7,
                "reminder_hours_before": 24,
                "overdue_reminder_cooldown_hours": 4,
                "high_urgency_cooldown_hours": 2,
                "finished_reminder_hours": 24,
                "timezone": "Europe/Moscow",
                "created_at": "1970-01-01T00:00:00+00:00",
                "updated_at": "1970-01-01T00:00:00+00:00",
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("status_logs")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_deadline", table_name="tasks")
    op.drop_index("ix_tasks_chat_message", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("uq_role_memberships_role_username", table_name="role_memberships")
    op.drop_index("uq_role_memberships_role_user_id", table_name="role_memberships")
    op.drop_index("ix_role_memberships_role", table_name="role_memberships")
    op.drop_table("role_memberships")
    op.drop_table("processed_messages")
    op.drop_table("parse_failures")
    op.drop_table("app_settings")
