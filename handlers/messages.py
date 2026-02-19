"""Main message handler — brief detection, edited messages."""

import structlog
from aiogram import Router
from aiogram.types import Message

from ai.classifier import classify_message
from core.brief_text_parser import parse_original_brief_sections
from core.config import runtime
from core.exceptions import AITransientError
from core.log_utils import message_log_context
from core.text_utils import compact_preview
from db.engine import async_session
from db.repo import message_repo, task_repo
from handlers.filters import WorkingChatFilter, WorkingTopicFilter, is_topic_root_reply
from services.brief_pipeline import process_brief
from services.postpone_service import maybe_process_pending_postpone
from services.task_service import sanitize_ai_data
from ui.cards import get_card_for_status

logger = structlog.get_logger()

router = Router()


def _is_command(message: Message) -> bool:
    text = message.text or ""
    return text.startswith("/")


@router.message(WorkingTopicFilter())
async def handle_customs_message(message: Message):
    """Silent reader: processes all messages in the Customs topic."""
    text = message.text or message.caption
    context = message_log_context(message, text)

    if _is_command(message):
        logger.info("message_skipped_command", **context)
        return

    if message.reply_to_message and not is_topic_root_reply(message):
        logger.info("message_skipped_reply", **context)
        return

    if await maybe_process_pending_postpone(message):
        logger.info("message_handled_by_pending_postpone", **context)
        return

    if not text:
        logger.info("message_skipped_no_text", **context)
        return

    async with async_session() as session:
        if await message_repo.is_message_processed(session, message.chat.id, message.message_id):
            logger.info("message_skipped_already_processed", **context)
            return

    logger.info("message_processing_started", **context)
    async with async_session() as session:
        await process_brief(message, session)


@router.message(WorkingChatFilter())
async def handle_message_in_customs_chat_other_topics(message: Message):
    """Diagnostics for messages in the configured chat but outside working topic."""
    if message.message_thread_id == runtime.customs_topic_id:
        return

    text = message.text or message.caption
    logger.info(
        "message_ignored_wrong_topic",
        expected_topic_id=runtime.customs_topic_id,
        text_preview=compact_preview(text),
        **message_log_context(message, text),
    )


@router.edited_message(WorkingTopicFilter())
async def handle_edited_message(message: Message):
    """Re-parse edited messages that are linked to tasks."""
    text = message.text or message.caption
    context = message_log_context(message, text)
    if not text:
        logger.info("edited_message_skipped_no_text", **context)
        return

    logger.info("edited_message_received", **context)

    async with async_session() as session:
        existing_task = await task_repo.get_task_by_message(session, message.chat.id, message.message_id)

    if not existing_task:
        logger.info("edited_message_not_linked_to_task_reprocessing", **context)
        async with async_session() as session:
            await process_brief(message, session)
        return

    logger.info("edited_message_reparse_started", task_id=existing_task.id, **context)

    has_photo = bool(message.photo)

    try:
        result = await classify_message(text, has_photo)
    except AITransientError:
        logger.warning("ai_transient_failure_on_edit", task_id=existing_task.id, **context)
        return

    if result is None:
        logger.warning("edited_message_ai_failed", task_id=existing_task.id, **context)
        return

    if not result.get("is_task"):
        logger.info(
            "edited_message_not_a_brief",
            task_id=existing_task.id,
            confidence=result.get("confidence"),
            ai_reason=result.get("reason"),
            **context,
        )
        return

    data = result.get("data", {})
    sanitize_ai_data(data)

    bot_message_id: int | None = None
    card_text: str | None = None
    keyboard = None
    chat_id: int | None = None

    async with async_session() as session:
        task = await task_repo.get_task_by_message(session, message.chat.id, message.message_id)
        if not task:
            logger.warning("edited_message_task_not_found", task_id=existing_task.id, **context)
            return

        task.raw_text = text
        original_sections = parse_original_brief_sections(text)
        task.task_date = data.get("task_date", task.task_date)
        task.fan_link = data.get("fan_link", task.fan_link)
        task.fan_name = data.get("fan_name", task.fan_name)
        task.platform = data.get("platform", task.platform)
        task.amount_total = data.get("amount_total", task.amount_total)
        task.amount_paid = data.get("amount_paid", task.amount_paid)
        task.amount_remaining = data.get("amount_remaining", task.amount_remaining)
        task.payment_note = data.get("payment_note", task.payment_note)
        task.duration = data.get("duration", task.duration)
        task.description = data.get("description", task.description)
        task.outfit = data.get("outfit", task.outfit)
        task.notes = data.get("notes", task.notes)
        task.description_original = original_sections["description_original"]
        task.outfit_original = original_sections["outfit_original"]
        task.notes_original = original_sections["notes_original"]
        task.priority = data.get("priority", task.priority)
        task.deadline = data.get("deadline", task.deadline)

        await session.commit()

        if task.bot_message_id:
            card_text, keyboard = get_card_for_status(task)
            bot_message_id = task.bot_message_id
            chat_id = task.chat_id

        task_id = task.id

    if bot_message_id and card_text is not None and chat_id is not None:
        try:
            await message.bot.edit_message_text(
                card_text,
                chat_id=chat_id,
                message_id=bot_message_id,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.error(
                "card_update_failed",
                task_id=task_id, bot_message_id=bot_message_id, error=str(e),
            )

    logger.info("task_updated_from_edit", task_id=task_id)
