import os
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import env

logger = structlog.get_logger()

# Ensure data directory exists
os.makedirs(os.path.dirname(env.db_path) or ".", exist_ok=True)

engine = create_async_engine(
    f"sqlite+aiosqlite:///{env.db_path}",
    echo=False,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Run Alembic migrations to bring DB schema up to date."""
    import asyncio

    from alembic import command
    from alembic.config import Config

    def _run_migrations():
        project_root = Path(__file__).resolve().parent.parent
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
        command.upgrade(alembic_cfg, "head")

    await asyncio.to_thread(_run_migrations)
    logger.info("database_initialized", path=env.db_path)
