"""Main scheduler loop — runs background jobs periodically."""

import asyncio
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot

from core.config import runtime
from core.constants import (
    MORNING_DIGEST_HOUR,
    RETRY_SCAN_INTERVAL,
)
from db.engine import async_session
from scheduler.jobs.morning_digest import send_morning_digest
from scheduler.jobs.retry_processor import process_ai_retry_queue

logger = structlog.get_logger()


def _local_now() -> datetime:
    try:
        return datetime.now(ZoneInfo(runtime.timezone))
    except Exception:
        return datetime.now(timezone.utc)


async def start_scheduler(bot: Bot) -> None:
    logger.info("scheduler_started")
    last_retry_scan_at: datetime | None = None
    last_morning_digest_date: date | None = None

    while True:
        sleep_seconds = 60.0
        try:
            now = datetime.now(timezone.utc)

            if last_retry_scan_at is None or (now - last_retry_scan_at) >= RETRY_SCAN_INTERVAL:
                async with async_session() as session:
                    await process_ai_retry_queue(bot, session)
                last_retry_scan_at = now

            local_now = _local_now()
            if (
                local_now.hour >= MORNING_DIGEST_HOUR
                and local_now.date() != last_morning_digest_date
            ):
                async with async_session() as session:
                    await send_morning_digest(bot, session)
                last_morning_digest_date = local_now.date()

            sleep_seconds = max(1.0, 60 - now.second - (now.microsecond / 1_000_000))

        except asyncio.CancelledError:
            logger.info("scheduler_cancelled")
            return
        except Exception as e:
            logger.error("scheduler_error", error=str(e))

        await asyncio.sleep(sleep_seconds)
