"""add ai retry queue

Revision ID: 0002_add_ai_retry_queue
Revises: 0001_initial_db_first
Create Date: 2026-02-16 02:05:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_ai_retry_queue"
down_revision: Union[str, Sequence[str], None] = "0001_initial_db_first"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_retry_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("has_photo", sa.Boolean(), nullable=False),
        sa.Column("sender_username", sa.String(length=100), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("first_enqueued_at", sa.String(length=30), nullable=False),
        sa.Column("next_retry_at", sa.String(length=30), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=30), nullable=False),
        sa.Column("updated_at", sa.String(length=30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_ai_retry_queue_chat_message",
        "ai_retry_queue",
        ["chat_id", "message_id"],
        unique=True,
    )
    op.create_index(
        "ix_ai_retry_queue_next_retry_at",
        "ai_retry_queue",
        ["next_retry_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_retry_queue_next_retry_at", table_name="ai_retry_queue")
    op.drop_index("uq_ai_retry_queue_chat_message", table_name="ai_retry_queue")
    op.drop_table("ai_retry_queue")
