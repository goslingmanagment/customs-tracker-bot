"""Deadline postpone callback actions, including quick-shift options."""

from datetime import datetime, timedelta

import structlog
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.log_utils import today_local
from db.repo import task_repo
from services.postpone_service import (
    clear_pending_postpone,
    clear_pending_postpone_prompt_markup,
    get_pending_postpone,
    postpone_status_error,
    set_pending_postpone,
)

from .common import (
    card_refresh_note,
    commit_session_safely,
    format_deadline_for_prompt,
    refresh_card,
    send_feedback,
    send_feedback_best_effort,
)

logger = structlog.get_logger()


def _postpone_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="+1 дн",
                    callback_data=f"task:{task_id}:postpone_1d",
                ),
                InlineKeyboardButton(
                    text="+3 дн",
                    callback_data=f"task:{task_id}:postpone_3d",
                ),
                InlineKeyboardButton(
                    text="+7 дн",
                    callback_data=f"task:{task_id}:postpone_7d",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"task:{task_id}:cancel_postpone",
                ),
            ],
        ]
    )


def _shift_deadline(deadline: str | None, days: int) -> tuple[str, str]:
    base_date = None
    if deadline:
        try:
            base_date = datetime.strptime(deadline, "%Y-%m-%d").date()
        except ValueError:
            base_date = None
    if base_date is None:
        base_date = datetime.strptime(today_local(), "%Y-%m-%d").date()

    new_date = base_date + timedelta(days=max(1, days))
    return new_date.strftime("%Y-%m-%d"), new_date.strftime("%d.%m.%Y")


async def action_postpone(callback, task, session, user, user_name, user_display):
    status_error = postpone_status_error(task.status)
    if status_error:
        await callback.answer(status_error)
        return
    previous_pending = get_pending_postpone(user.id)
    if previous_pending:
        await clear_pending_postpone_prompt_markup(callback.bot, previous_pending)
    current_deadline = format_deadline_for_prompt(task.deadline)
    prompt_message = await send_feedback(
        callback.bot,
        task,
        (
            f"⏰ <b>Кастом #{task.id:03d} — перенос дедлайна</b>\n"
            f"{user_display}, текущий дедлайн: {current_deadline}\n"
            "Выберите быстрый перенос кнопкой ниже или введите дату вручную "
            "(ДД.ММ или ДД.ММ.ГГГГ).\n"
            "Ожидание ввода: 120 секунд."
        ),
        reply_markup=_postpone_keyboard(task.id),
    )
    set_pending_postpone(
        user_id=user.id,
        task_id=task.id,
        chat_id=task.chat_id,
        topic_id=task.topic_id,
        prompt_message_id=prompt_message.message_id,
    )
    await callback.answer("Ожидаю дату (120 сек)")


async def action_cancel_postpone(callback, task, session, user, user_name, user_display):
    pending = get_pending_postpone(user.id)
    if not pending or pending.task_id != task.id:
        if callback.message:
            try:
                await callback.bot.edit_message_reply_markup(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=None,
                )
            except Exception as exc:
                logger.error(
                    "postpone_stale_markup_clear_failed",
                    task_id=task.id,
                    error=str(exc),
                )
        await callback.answer("Нет активного ожидания даты для этого кастома")
        return
    clear_pending_postpone(user.id)
    if callback.message:
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                reply_markup=None,
            )
        except Exception as exc:
            logger.error(
                "postpone_cancel_markup_clear_failed",
                task_id=task.id,
                error=str(exc),
            )
    await send_feedback(
        callback.bot,
        task,
        f"❎ {user_display} отменил(а) перенос дедлайна для кастома #{task.id:03d}",
    )
    await callback.answer("Перенос отменён")


async def _action_postpone_quick(
    callback,
    task,
    session,
    user,
    user_name,
    user_display,
    days: int,
):
    pending = get_pending_postpone(user.id)
    if not pending or pending.task_id != task.id:
        if callback.message:
            try:
                await callback.bot.edit_message_reply_markup(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    reply_markup=None,
                )
            except Exception:
                pass
        await callback.answer("Сессия переноса неактивна. Нажмите ⏰ снова.")
        return

    status_error = postpone_status_error(task.status)
    if status_error:
        clear_pending_postpone(user.id)
        await clear_pending_postpone_prompt_markup(callback.bot, pending)
        await callback.answer(status_error)
        return

    old_deadline = task.deadline
    old_display = format_deadline_for_prompt(old_deadline)
    new_deadline, new_display = _shift_deadline(old_deadline, days)
    await task_repo.update_task_deadline(
        session,
        task,
        new_deadline,
        changed_by_id=user.id,
        changed_by_name=user_name,
    )
    if not await commit_session_safely(
        session,
        callback,
        action=f"postpone_{days}d",
        task_id=task.id,
    ):
        clear_pending_postpone(user.id)
        await clear_pending_postpone_prompt_markup(callback.bot, pending)
        return

    card_refreshed = await refresh_card(callback, task)
    clear_pending_postpone(user.id)
    await clear_pending_postpone_prompt_markup(callback.bot, pending)

    await callback.answer(f"Перенесено на +{days} дн.")
    feedback = (
        f"📅 {user_display} перенёс(ла) дедлайн кастома #{task.id:03d}: "
        f"{old_display} → {new_display}"
    )
    if not card_refreshed:
        feedback += card_refresh_note(task.id)
    await send_feedback_best_effort(
        callback.bot,
        task,
        feedback,
        event=f"postpone_{days}d_feedback",
    )


async def action_postpone_1d(callback, task, session, user, user_name, user_display):
    await _action_postpone_quick(
        callback, task, session, user, user_name, user_display, days=1
    )


async def action_postpone_3d(callback, task, session, user, user_name, user_display):
    await _action_postpone_quick(
        callback, task, session, user, user_name, user_display, days=3
    )


async def action_postpone_7d(callback, task, session, user, user_name, user_display):
    await _action_postpone_quick(
        callback, task, session, user, user_name, user_display, days=7
    )
