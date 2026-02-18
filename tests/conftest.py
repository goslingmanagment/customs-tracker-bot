from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import env, roles, runtime
from db.models import Base


@pytest.fixture(autouse=True)
def _reset_global_singletons():
    env_snapshot = {
        "bot_token": env.bot_token,
        "anthropic_api_key": env.anthropic_api_key,
        "db_path": env.db_path,
        "log_level": env.log_level,
        "web_enabled": env.web_enabled,
        "web_host": env.web_host,
        "web_port": env.web_port,
        "web_secret_key": env.web_secret_key,
        "web_admin_code": env.web_admin_code,
        "web_model_code": env.web_model_code,
        "web_teamlead_code": env.web_teamlead_code,
        "web_cookie_ttl_days": env.web_cookie_ttl_days,
        "web_cookie_secure": env.web_cookie_secure,
    }
    runtime_snapshot = asdict(runtime)
    roles_snapshot = asdict(roles)

    yield

    env.bot_token = env_snapshot["bot_token"]
    env.anthropic_api_key = env_snapshot["anthropic_api_key"]
    env.db_path = env_snapshot["db_path"]
    env.log_level = env_snapshot["log_level"]
    env.web_enabled = env_snapshot["web_enabled"]
    env.web_host = env_snapshot["web_host"]
    env.web_port = env_snapshot["web_port"]
    env.web_secret_key = env_snapshot["web_secret_key"]
    env.web_admin_code = env_snapshot["web_admin_code"]
    env.web_model_code = env_snapshot["web_model_code"]
    env.web_teamlead_code = env_snapshot["web_teamlead_code"]
    env.web_cookie_ttl_days = env_snapshot["web_cookie_ttl_days"]
    env.web_cookie_secure = env_snapshot["web_cookie_secure"]

    runtime.customs_chat_id = runtime_snapshot["customs_chat_id"]
    runtime.customs_topic_id = runtime_snapshot["customs_topic_id"]
    runtime.ai_model = runtime_snapshot["ai_model"]
    runtime.ai_confidence_threshold = runtime_snapshot["ai_confidence_threshold"]
    runtime.reminder_hours_before = runtime_snapshot["reminder_hours_before"]
    runtime.overdue_reminder_cooldown_hours = runtime_snapshot[
        "overdue_reminder_cooldown_hours"
    ]
    runtime.high_urgency_cooldown_hours = runtime_snapshot[
        "high_urgency_cooldown_hours"
    ]
    runtime.finished_reminder_hours = runtime_snapshot["finished_reminder_hours"]
    runtime.timezone = runtime_snapshot["timezone"]

    roles.admin_ids = list(roles_snapshot["admin_ids"])
    roles.admin_usernames = list(roles_snapshot["admin_usernames"])
    roles.model_ids = list(roles_snapshot["model_ids"])
    roles.model_usernames = list(roles_snapshot["model_usernames"])
    roles.teamlead_ids = list(roles_snapshot["teamlead_ids"])
    roles.teamlead_usernames = list(roles_snapshot["teamlead_usernames"])


@pytest.fixture
async def db_engine(tmp_path: Path):
    db_file = tmp_path / "test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def db_session_factory(db_engine):
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(db_session_factory):
    async with db_session_factory() as session:
        yield session


@pytest.fixture
def freeze_time(monkeypatch):
    def _freeze(module, frozen: datetime, attr: str = "datetime"):
        if frozen.tzinfo is None:
            frozen_utc = frozen.replace(tzinfo=timezone.utc)
        else:
            frozen_utc = frozen.astimezone(timezone.utc)

        class _FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return frozen_utc.replace(tzinfo=None)
                return frozen_utc.astimezone(tz)

            @classmethod
            def fromisoformat(cls, value: str):
                return datetime.fromisoformat(value)

            @classmethod
            def strptime(cls, value: str, fmt: str):
                return datetime.strptime(value, fmt)

        monkeypatch.setattr(module, attr, _FrozenDateTime)

    return _freeze
