"""Manual brief registration via /add command."""

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ai.classifier import classify_message
from core.brief_text_parser import parse_original_brief_sections
from core.exceptions import AITransientError
from core.permissions import can_add_brief
from core.text_utils import esc
from db.engine import async_session
from db.repo import message_repo, task_repo
from diagnostics.readiness import (
    evaluate_brief_env_readiness,
    summarize_readiness_for_log,
)
from handlers.filters import WorkingTopicFilter
from services.role_service import resolve_known_roles
from services.task_service import build_task_kwargs, sanitize_ai_data
from ui.cards import build_draft_card

logger = structlog.get_logger()

router = Router()


@router.message(Command("add"), WorkingTopicFilter())
async def cmd_add(message: Message):
    """Manual brief registration — use as a reply to a message."""
    if not can_add_brief(message.from_user):
        await message.reply(
            "Только администраторы, модели и тимлиды могут добавлять бриф вручную"
        )
        return

    async with async_session() as session:
        await resolve_known_roles(message.from_user, session)

    replied = message.reply_to_message
    if not replied:
        await message.reply("Используйте /add как ответ на сообщение с брифом")
        return

    text = replied.text or replied.caption
    if not text:
        await message.reply("В сообщении нет текста для парсинга")
        return

    async with async_session() as session:
        existing = await task_repo.get_task_by_message(session, replied.chat.id, replied.message_id)
        if existing:
            await message.reply(f"Этот бриф уже зарегистрирован как кастом #{existing.id:03d}")
            return

    readiness = evaluate_brief_env_readiness()
    if not readiness.ready:
        logger.warning(
            "manual_add_blocked_by_env",
            command_message_id=message.message_id,
            command_chat_id=message.chat.id,
            command_topic_id=message.message_thread_id,
            command_from_user_id=message.from_user.id if message.from_user else None,
            command_from_username=message.from_user.username if message.from_user else None,
            replied_message_id=replied.message_id,
            replied_chat_id=replied.chat.id,
            **summarize_readiness_for_log(readiness),
        )
        await message.reply(
            "❌ Создание брифа сейчас недоступно: конфигурация не готова.\n"
            "Проверьте /health."
        )
        return

    has_photo = bool(replied.photo)

    try:
        result = await classify_message(text, has_photo)
    except AITransientError:
        await message.reply("Ошибка AI — попробуйте позже")
        return

    if result is None:
        async with async_session() as session:
            await message_repo.log_parse_failure(
                session, replied.message_id, text, "api_error",
                "AI returned invalid result on /add"
            )
            await session.commit()
        await message.reply("AI вернул некорректный ответ, попробуйте позже")
        return

    is_task = result.get("is_task", False)
    data = result.get("data", {})
    confidence = result.get("confidence", 0) or 0
    reason = esc(result.get("reason", "неизвестно"))

    if is_task:
        sanitize_ai_data(data)

    async with async_session() as session:
        # Re-check inside transaction for race safety
        existing = await task_repo.get_task_by_message(session, replied.chat.id, replied.message_id)
        if existing:
            await message.reply(f"Этот бриф уже зарегистрирован как кастом #{existing.id:03d}")
            return

        if is_task:
            kwargs = build_task_kwargs(
                data,
                message_id=replied.message_id,
                chat_id=replied.chat.id,
                topic_id=replied.message_thread_id,
                raw_text=text,
                ai_confidence=confidence,
                sender_username=replied.from_user.username if replied.from_user else None,
            )
        else:
            original_sections = parse_original_brief_sections(text)
            kwargs = {
                "message_id": replied.message_id,
                "chat_id": replied.chat.id,
                "topic_id": replied.message_thread_id,
                "raw_text": text,
                "description": text[:200],
                "description_original": original_sections["description_original"],
                "outfit_original": original_sections["outfit_original"],
                "notes_original": original_sections["notes_original"],
                "priority": "medium",
                "ai_confidence": confidence or 0,
            }

        try:
            task, created = await task_repo.create_task(session, **kwargs)
        except Exception as e:
            logger.error("manual_task_create_failed", message_id=replied.message_id, error=str(e))
            await message.reply("Не удалось создать кастом, попробуйте позже")
            return

        if not created:
            await message_repo.mark_message_processed(
                session, replied.chat.id, replied.message_id, is_task=True
            )
            await session.commit()
            await message.reply(f"Этот бриф уже зарегистрирован как кастом #{task.id:03d}")
            return

        card_text, keyboard = build_draft_card(task)
        try:
            sent = await replied.reply(card_text, reply_markup=keyboard)
        except Exception as e:
            await session.rollback()
            logger.error("manual_task_card_send_failed", message_id=replied.message_id, error=str(e))
            await message.reply("Не удалось отправить карточку кастома, попробуйте снова")
            return

        await task_repo.update_task_bot_message_id(session, task, sent.message_id)
        await session.commit()

        await message_repo.mark_message_processed(
            session, replied.chat.id, replied.message_id, is_task=True
        )
        await session.commit()

        if is_task:
            await message.reply(f"✅ Кастом #{task.id:03d} создан вручную")
        else:
            await message.reply(
                f"⚠️ AI не распознал бриф (причина: {reason}), "
                f"но задача создана вручную как черновик #{task.id:03d}."
            )
