"""Core brief processing pipeline: pre-filter → AI classify → create task."""

import structlog
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from ai.classifier import classify_message
from core.config import roles, runtime
from core.exceptions import AITransientError
from core.log_utils import message_log_context
from db.repo import message_repo, retry_repo, task_repo
from diagnostics.readiness import (
    evaluate_brief_env_readiness,
    summarize_readiness_for_log,
)
from pre_filter import evaluate_message_for_processing
from services.task_service import build_task_kwargs, sanitize_ai_data
from ui.cards import build_draft_card

logger = structlog.get_logger()


def _admin_mentions() -> str:
    mentions: list[str] = []
    for username in roles.admin_usernames:
        if username:
            mentions.append(f"@{username}")
    for user_id in roles.admin_ids:
        mentions.append(f'<a href="tg://user?id={int(user_id)}">admin</a>')
    deduped: list[str] = []
    for mention in mentions:
        if mention not in deduped:
            deduped.append(mention)
    return " ".join(deduped)


async def _notify_admins(
    message: Message,
    text: str,
    *,
    event: str,
    task_id: int | None = None,
) -> None:
    mentions = _admin_mentions()
    if not mentions:
        return
    try:
        await message.bot.send_message(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            reply_to_message_id=message.message_id,
            text=f"⚠️ Для админов: {text}\n{mentions}",
        )
    except Exception as exc:
        logger.error(
            "admin_notification_failed",
            event=event,
            task_id=task_id,
            error=str(exc),
            message_id=message.message_id,
            chat_id=message.chat.id,
        )


async def _notify_admins_about_ai_failure(message: Message) -> None:
    await _notify_admins(
        message,
        (
            "AI не смог классифицировать сообщение.\n"
            "Используйте /add ответом на сообщение, чтобы зарегистрировать вручную."
        ),
        event="ai_classification_failed",
    )


async def _notify_admins_about_operational_issue(
    message: Message,
    text: str,
    *,
    task_id: int | None = None,
) -> None:
    await _notify_admins(
        message,
        text,
        event="brief_pipeline_operational_issue",
        task_id=task_id,
    )


async def process_brief(message: Message, session: AsyncSession) -> None:
    """Full pipeline: pre-filter → AI → DB → card."""
    text = message.text or message.caption
    context = message_log_context(message, text)
    if not text:
        logger.info("brief_pipeline_skipped_no_text", **context)
        return

    readiness = evaluate_brief_env_readiness()
    if not readiness.ready:
        logger.warning(
            "brief_pipeline_blocked_by_env",
            **context,
            **summarize_readiness_for_log(readiness),
        )
        return

    logger.info("brief_pipeline_started", **context)

    # Pre-filter (quick, no AI)
    should_process, prefilter_reason, prefilter_details = (
        evaluate_message_for_processing(message)
    )
    prefilter_context = {**context, **prefilter_details, "reason": prefilter_reason}
    if not should_process:
        await message_repo.mark_message_processed(session, message.chat.id, message.message_id)
        await session.commit()
        logger.info("message_filtered_out", **prefilter_context)
        return

    logger.info("message_prefilter_passed", **prefilter_context)

    # AI classification (slow network I/O — run outside heavy DB work)
    has_photo = bool(message.photo)
    logger.info("ai_classification_requested", **context)

    try:
        result = await classify_message(text, has_photo)
    except AITransientError:
        await retry_repo.enqueue_ai_retry(
            session,
            chat_id=message.chat.id,
            message_id=message.message_id,
            topic_id=message.message_thread_id,
            raw_text=text,
            has_photo=has_photo,
            sender_username=message.from_user.username if message.from_user else None,
            error_detail="TRANSIENT_ERROR",
        )
        await session.commit()
        logger.warning("ai_transient_failure_enqueued", **context)
        return

    if result is None:
        await message_repo.log_parse_failure(
            session, message.message_id, text, "api_error", "AI returned None"
        )
        await message_repo.mark_message_processed(session, message.chat.id, message.message_id)
        await session.commit()
        await _notify_admins_about_ai_failure(message)
        logger.error("ai_classification_failed_permanent", **context)
        return

    is_task = result.get("is_task", False)
    confidence = result.get("confidence", 0)

    if not is_task or confidence < runtime.ai_confidence_threshold:
        await message_repo.mark_message_processed(session, message.chat.id, message.message_id)
        await session.commit()
        if is_task:
            logger.info("low_confidence_brief", confidence=confidence,
                        threshold=runtime.ai_confidence_threshold, **context)
        else:
            logger.info("message_classified_not_brief", confidence=confidence,
                        ai_reason=result.get("reason"), **context)
        return

    # It's a brief — extract data and create task
    data = sanitize_ai_data(result.get("data", {}))

    # Idempotency: skip if task already exists for this message
    existing = await task_repo.get_task_by_message(session, message.chat.id, message.message_id)
    if existing:
        await message_repo.mark_message_processed(
            session, message.chat.id, message.message_id, is_task=True
        )
        await session.commit()
        logger.info("task_already_exists", task_id=existing.id, **context)
        return

    kwargs = build_task_kwargs(
        data,
        message_id=message.message_id,
        chat_id=message.chat.id,
        topic_id=message.message_thread_id,
        raw_text=text,
        ai_confidence=confidence,
        sender_username=message.from_user.username if message.from_user else None,
    )

    try:
        task, created = await task_repo.create_task(session, **kwargs)
    except Exception as e:
        await session.rollback()
        logger.error("task_create_failed", error=str(e), **context)
        try:
            await message_repo.log_parse_failure(
                session,
                message.message_id,
                text,
                "task_create_failed",
                str(e),
            )
            await session.commit()
        except Exception as persist_exc:
            await session.rollback()
            logger.error(
                "task_create_failure_persist_failed",
                error=str(persist_exc),
                **context,
            )
        await _notify_admins_about_operational_issue(
            message,
            (
                "Не удалось сохранить распознанный бриф в базе. "
                "Проверьте сообщение вручную и используйте /add."
            ),
        )
        return

    if not created:
        await message_repo.mark_message_processed(
            session, message.chat.id, message.message_id, is_task=True
        )
        await session.commit()
        logger.info("task_create_race_recovered", task_id=task.id, **context)
        return

    try:
        await message_repo.mark_message_processed(
            session, message.chat.id, message.message_id, is_task=True
        )
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(
            "task_persist_commit_failed",
            task_id=task.id,
            error=str(e),
            **context,
        )
        await _notify_admins_about_operational_issue(
            message,
            (
                f"Кастом #{task.id:03d} не удалось полностью сохранить. "
                "Проверьте сообщение вручную и используйте /add при необходимости."
            ),
            task_id=task.id,
        )
        return

    # Send confirmation card after durable persistence.
    card_text, keyboard = build_draft_card(task)
    try:
        sent = await message.reply(card_text, reply_markup=keyboard)
    except Exception as e:
        logger.error("task_card_send_failed", task_id=task.id, error=str(e), **context)
        await _notify_admins_about_operational_issue(
            message,
            (
                f"Кастом #{task.id:03d} сохранён, но карточку не удалось отправить. "
                f"Откройте /task {task.id}."
            ),
            task_id=task.id,
        )
        return

    try:
        await task_repo.update_task_bot_message_id(session, task, sent.message_id)
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(
            "task_bot_message_bind_failed",
            task_id=task.id,
            bot_message_id=sent.message_id,
            error=str(e),
            **context,
        )
        await _notify_admins_about_operational_issue(
            message,
            (
                f"Кастом #{task.id:03d} сохранён, но привязка карточки не удалась. "
                f"Проверьте /task {task.id}."
            ),
            task_id=task.id,
        )
        return

    logger.info(
        "brief_recognized",
        task_id=task.id,
        confidence=confidence,
        amount=task.amount_total,
        bot_message_id=sent.message_id,
        **context,
    )
