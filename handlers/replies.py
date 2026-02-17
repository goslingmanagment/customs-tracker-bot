"""Reply handler — shot/delivery keyword detection and date-reply fallback."""

import re

import structlog
from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.constants import DELIVERED_KEYWORDS, SHOT_KEYWORDS
from core.log_utils import message_log_context
from core.permissions import is_admin_or_teamlead, is_detection_actor
from db.engine import async_session
from db.repo import message_repo, task_repo
from handlers.filters import WorkingTopicFilter, is_topic_root_reply
from services.brief_pipeline import process_brief
from services.postpone_service import maybe_process_pending_postpone, process_deadline_change_text
from services.role_service import resolve_known_roles

logger = structlog.get_logger()

router = Router()

TIMECODE_PATTERN = re.compile(r"\d{1,3}:\d{2}")


def looks_like_shot_report(text: str) -> bool:
    text_lower = text.lower()
    if TIMECODE_PATTERN.search(text):
        return True
    return any(kw in text_lower for kw in SHOT_KEYWORDS)


def looks_like_delivery_report(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in DELIVERED_KEYWORDS)


@router.message(WorkingTopicFilter(), F.reply_to_message)
async def handle_reply(message: Message):
    # Skip fake topic-root replies — process as normal topic messages.
    if is_topic_root_reply(message):
        text = message.text or message.caption
        if not text or text.startswith("/"):
            return
        if await maybe_process_pending_postpone(message):
            return
        async with async_session() as session:
            await process_brief(message, session)
        return

    text = message.text or message.caption
    context = message_log_context(message, text)
    logger.info("reply_received", **context)

    if await maybe_process_pending_postpone(message):
        logger.info("reply_handled_by_pending_postpone", **context)
        return

    if not text:
        logger.info("reply_skipped_no_text", **context)
        return

    replied_to = message.reply_to_message
    if not replied_to:
        logger.info("reply_skipped_no_replied_message", **context)
        return

    should_process_as_brief = False

    async with async_session() as session:
        task = await task_repo.get_task_by_message(session, message.chat.id, replied_to.message_id)
        if not task:
            task = await task_repo.get_task_by_bot_message(session, message.chat.id, replied_to.message_id)

        if not task:
            already_processed = await message_repo.is_message_processed(
                session, message.chat.id, message.message_id
            )
            should_process_as_brief = not already_processed
            logger.info(
                "reply_not_linked_to_task",
                already_processed=already_processed,
                should_process_as_brief=should_process_as_brief,
                **context,
            )
        else:
            logger.info(
                "reply_linked_to_task",
                task_id=task.id, task_status=task.status, **context,
            )

            if is_detection_actor(message.from_user):
                await resolve_known_roles(message.from_user, session)

                if task.status == "processing" and looks_like_shot_report(text):
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[[
                            InlineKeyboardButton(
                                text="✅ Да",
                                callback_data=f"task:{task.id}:confirm_shot",
                            ),
                            InlineKeyboardButton(
                                text="❌ Нет",
                                callback_data=f"task:{task.id}:deny_shot",
                            ),
                        ]]
                    )
                    await message.reply(
                        f"📹 Отчёт о съёмке для кастома #{task.id:03d}?\nОтметить как отснято?",
                        reply_markup=keyboard,
                    )
                    logger.info("reply_shot_confirmation_prompt_sent", task_id=task.id, **context)
                    return

                if (
                    task.status == "finished"
                    and looks_like_delivery_report(text)
                    and is_admin_or_teamlead(message.from_user)
                ):
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[[
                            InlineKeyboardButton(
                                text="✅ Да",
                                callback_data=f"task:{task.id}:confirm_delivered",
                            ),
                            InlineKeyboardButton(
                                text="❌ Нет",
                                callback_data=f"task:{task.id}:deny_delivered",
                            ),
                        ]]
                    )
                    await message.reply(
                        f"📤 Кастом #{task.id:03d} доставлен фану?\nОтметить как выполненный?",
                        reply_markup=keyboard,
                    )
                    logger.info("reply_delivery_confirmation_prompt_sent", task_id=task.id, **context)
                    return

            # Reply-based fallback: date reply to bot card.
            if replied_to.from_user and replied_to.from_user.is_bot:
                postpone_status = await process_deadline_change_text(
                    session=session, message=message, task=task, text=text,
                )
                if postpone_status == "no_match":
                    logger.info("reply_to_bot_message_no_deadline_pattern", task_id=task.id, **context)
                else:
                    logger.info(
                        "reply_deadline_change_processed",
                        task_id=task.id, result=postpone_status, **context,
                    )
                return

            logger.info("reply_linked_to_task_no_action", task_id=task.id, **context)

    if should_process_as_brief:
        logger.info("reply_fallback_to_brief_pipeline", **context)
        async with async_session() as session:
            await process_brief(message, session)
