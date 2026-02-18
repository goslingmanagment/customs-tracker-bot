from dataclasses import dataclass, field

from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvConfig(BaseSettings):
    """Immutable secrets & infra from .env. Loaded once at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    bot_token: str = ""
    anthropic_api_key: str = ""
    db_path: str = "data/customs.db"
    log_level: str = "INFO"

    # Web dashboard
    web_enabled: bool = False
    web_host: str = "127.0.0.1"
    web_port: int = 8080
    web_secret_key: str = ""
    web_admin_code: str = ""
    web_model_code: str = ""
    web_teamlead_code: str = ""
    web_cookie_ttl_days: int = 7
    web_cookie_secure: bool = False


@dataclass
class RuntimeConfig:
    """Mutable runtime settings loaded from DB at startup."""

    customs_chat_id: int = 0
    customs_topic_id: int = 0
    ai_model: str = "claude-sonnet-4-5-20250929"
    ai_confidence_threshold: float = 0.7
    reminder_hours_before: int = 24
    overdue_reminder_cooldown_hours: int = 4
    high_urgency_cooldown_hours: int = 2
    finished_reminder_hours: int = 24
    timezone: str = "Europe/Moscow"


@dataclass
class RoleCache:
    """In-memory role lookup populated from DB."""

    admin_ids: list[int] = field(default_factory=list)
    admin_usernames: list[str] = field(default_factory=list)
    model_ids: list[int] = field(default_factory=list)
    model_usernames: list[str] = field(default_factory=list)
    teamlead_ids: list[int] = field(default_factory=list)
    teamlead_usernames: list[str] = field(default_factory=list)


# Module-level singletons
env = EnvConfig()
runtime = RuntimeConfig()
roles = RoleCache()
