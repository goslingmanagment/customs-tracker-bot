"""Embedded uvicorn server for running alongside the bot."""

import asyncio

import structlog
import uvicorn

from core.config import env

logger = structlog.get_logger()


async def create_web_server():
    """Create and start an embedded uvicorn server.

    Returns (server, task) so the caller can signal shutdown via
    server.should_exit = True and await the task.
    """
    from web.app import create_app

    app = create_app()
    config = uvicorn.Config(
        app=app,
        host=env.web_host,
        port=env.web_port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    # Disable signal handlers — bot.py owns SIGINT/SIGTERM
    server.install_signal_handlers = lambda: None

    task = asyncio.create_task(server.serve())

    logger.info(
        "web_server_started",
        host=env.web_host,
        port=env.web_port,
    )
    return server, task
