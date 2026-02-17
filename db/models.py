from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Telegram binding
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topic_id: Mapped[int | None] = mapped_column(BigInteger)
    bot_message_id: Mapped[int | None] = mapped_column(BigInteger)
    sender_username: Mapped[str | None] = mapped_column(String(100))

    # Task data (from AI parsing)
    task_date: Mapped[str | None] = mapped_column(String(20))
    fan_link: Mapped[str | None] = mapped_column(String(500))
    fan_name: Mapped[str | None] = mapped_column(String(200))
    platform: Mapped[str | None] = mapped_column(String(20))
    amount_total: Mapped[float | None] = mapped_column(Float)
    amount_paid: Mapped[float | None] = mapped_column(Float)
    amount_remaining: Mapped[float | None] = mapped_column(Float)
    payment_note: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    outfit: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    deadline: Mapped[str | None] = mapped_column(String(20))

    # Status
    status: Mapped[str] = mapped_column(String(20), default="draft")

    finished_at: Mapped[str | None] = mapped_column(String(30))
    delivered_at: Mapped[str | None] = mapped_column(String(30))

    # Metadata
    raw_text: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    last_reminder_at: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(30),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        onupdate=lambda: datetime.now(timezone.utc).isoformat(),
    )

    # Relationships
    status_logs: Mapped[list["StatusLog"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_deadline", "deadline"),
        Index("ix_tasks_chat_message", "chat_id", "message_id", unique=True),
    )


class StatusLog(Base):
    __tablename__ = "status_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by_id: Mapped[int | None] = mapped_column(BigInteger)
    changed_by_name: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )

    task: Mapped["Task"] = relationship(back_populates="status_logs")


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    is_task: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )


class ParseFailure(Base):
    __tablename__ = "parse_failures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[str] = mapped_column(String(50), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )


class AIRetryQueue(Base):
    __tablename__ = "ai_retry_queue"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    topic_id: Mapped[int | None] = mapped_column(BigInteger)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    has_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    sender_username: Mapped[str | None] = mapped_column(String(100))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    first_enqueued_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )
    next_retry_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(30),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        onupdate=lambda: datetime.now(timezone.utc).isoformat(),
    )

    __table_args__ = (
        Index("uq_ai_retry_queue_chat_message", "chat_id", "message_id", unique=True),
        Index("ix_ai_retry_queue_next_retry_at", "next_retry_at"),
    )


class RoleMembership(Base):
    __tablename__ = "role_memberships"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(30),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        onupdate=lambda: datetime.now(timezone.utc).isoformat(),
    )
    created_by_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by_name: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        Index("ix_role_memberships_role", "role"),
        Index("uq_role_memberships_role_user_id", "role", "user_id", unique=True),
        Index("uq_role_memberships_role_username", "role", "username", unique=True),
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    customs_chat_id: Mapped[int] = mapped_column(BigInteger, default=0)
    customs_topic_id: Mapped[int] = mapped_column(BigInteger, default=0)
    ai_model: Mapped[str] = mapped_column(String(128), default="claude-sonnet-4-5-20250929")
    ai_confidence_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    reminder_hours_before: Mapped[int] = mapped_column(default=24)
    overdue_reminder_cooldown_hours: Mapped[int] = mapped_column(default=4)
    high_urgency_cooldown_hours: Mapped[int] = mapped_column(default=2)
    finished_reminder_hours: Mapped[int] = mapped_column(default=24)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(30),
        default=lambda: datetime.now(timezone.utc).isoformat(),
        onupdate=lambda: datetime.now(timezone.utc).isoformat(),
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )
