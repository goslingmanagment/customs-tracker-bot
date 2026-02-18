"""Entrypoint — wiring only."""

import asyncio
import logging
import sys

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import env, runtime
from core.exceptions import StartupConfigError
from db.engine import async_session, init_db
from db.repo import settings_repo
from diagnostics.readiness import (
    build_startup_config_error,
    evaluate_startup_readiness,
    summarize_readiness_for_log,
)
from handlers.callbacks import router as callback_router
from handlers.commands.brief import router as brief_router
from handlers.commands.info import router as info_router
from handlers.commands.roles import router as roles_router
from handlers.commands.settings import router as settings_router
from handlers.commands.setup import router as setup_router
from handlers.commands.stats import router as stats_router
from handlers.commands.tasks import router as tasks_router
from handlers.messages import router as message_router
from handlers.middleware import UpdateLogMiddleware
from handlers.replies import router as reply_router
from scheduler.runner import start_scheduler
from services.role_service import load_role_cache
from services.settings_service import load_runtime_settings


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, env.log_level.upper(), logging.INFO),
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )


async def main() -> None:
    setup_logging()
    logger = structlog.get_logger()

    startup = evaluate_startup_readiness()
    logger.info(
        "startup_check",
        **summarize_readiness_for_log(startup.readiness),
    )
    if startup.non_fatal_blockers:
        logger.warning(
            "brief_env_startup_non_fatal_blockers",
            blockers=startup.non_fatal_blockers,
            blocker_count=len(startup.non_fatal_blockers),
            note="bot_will_continue",
        )
    if startup.fatal_blockers:
        logger.error(
            "brief_env_startup_fatal_blockers",
            blockers=startup.fatal_blockers,
            blocker_count=len(startup.fatal_blockers),
            note="bot_will_exit",
        )
        raise build_startup_config_error(startup)

    await init_db()

    async with async_session() as session:
        await settings_repo.ensure_app_settings_row(session)
        await session.commit()

    async with async_session() as session:
        runtime_cfg = await load_runtime_settings(session)
        logger.info("runtime_settings_loaded", **runtime_cfg)

    async with async_session() as session:
        cache = await load_role_cache(session)
        logger.info(
            "roles_cache_loaded",
            admin_count=len(cache["admin"]["ids"]) + len(cache["admin"]["usernames"]),
            model_count=len(cache["model"]["ids"]) + len(cache["model"]["usernames"]),
            teamlead_count=len(cache["teamlead"]["ids"]) + len(cache["teamlead"]["usernames"]),
        )

    bot = Bot(
        token=env.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.update.outer_middleware(UpdateLogMiddleware())

    # Register routers (order matters — setup first, then commands, replies, general messages)
    dp.include_router(setup_router)
    dp.include_router(info_router)
    dp.include_router(roles_router)
    dp.include_router(settings_router)
    dp.include_router(tasks_router)
    dp.include_router(brief_router)
    dp.include_router(stats_router)
    dp.include_router(callback_router)
    dp.include_router(reply_router)
    dp.include_router(message_router)

    scheduler_task = asyncio.create_task(start_scheduler(bot))

    # Conditionally start web server
    web_server = None
    web_task = None
    if env.web_enabled and env.web_secret_key:
        from web.server import create_web_server

        web_server, web_task = await create_web_server()
    elif env.web_enabled and not env.web_secret_key:
        logger.warning("web_server_skipped", reason="WEB_SECRET_KEY is not set")

    logger.info(
        "bot_starting",
        chat_id=runtime.customs_chat_id,
        topic_id=runtime.customs_topic_id,
        web_enabled=env.web_enabled and bool(env.web_secret_key),
    )

    try:
        await dp.start_polling(bot)
    finally:
        if web_server:
            web_server.should_exit = True
        if web_task:
            await web_task
        scheduler_task.cancel()
        logger.info("bot_stopped")


def run() -> int:
    try:
        asyncio.run(main())
    except StartupConfigError as error:
        print(error.render_terminal(), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
