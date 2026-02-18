"""Delete/not-a-brief callback actions."""

import structlog
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db.repo import task_repo

from .common import (
    commit_session_safely,
    consume_delete_confirmation,
    refresh_card,
    send_feedback,
    send_feedback_best_effort,
    set_delete_confirmation,
    clear_delete_confirmation,
    safe_delete_message,
)

logger = structlog.get_logger()


async def action_not_task(callback, task, session, user, user_name, user_display):
    if task.status != "draft":
        await callback.answer("Удаление доступно только для черновика")
        return
    set_delete_confirmation(user.id, task.id)
    confirm_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚠️ Точно удалить?",
                    callback_data=f"task:{task.id}:not_task_confirm",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Отмена",
                    callback_data=f"task:{task.id}:not_task_cancel",
                ),
            ],
        ]
    )
    if callback.message:
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=task.chat_id,
                message_id=callback.message.message_id,
                reply_markup=confirm_keyboard,
            )
        except Exception as exc:
            logger.error(
                "not_task_confirmation_edit_failed",
                task_id=task.id,
                error=str(exc),
            )
            await callback.answer("Не удалось показать подтверждение удаления")
            return
    else:
        await send_feedback(
            callback.bot,
            task,
            (
                f"⚠️ Подтвердите удаление кастома #{task.id:03d} "
                "в течение 10 секунд"
            ),
            reply_markup=confirm_keyboard,
        )
    await callback.answer("Нажмите «Точно удалить?» в течение 10 секунд")


async def action_not_task_confirm(callback, task, session, user, user_name, user_display):
    if task.status != "draft":
        await callback.answer("Удаление доступно только для черновика")
        return
    if not consume_delete_confirmation(user.id, task.id):
        await refresh_card(callback, task)
        await callback.answer("Подтверждение истекло. Нажмите «Не бриф» снова")
        return
    await task_repo.delete_task(session, task)
    if not await commit_session_safely(
        session, callback, action="not_task_confirm", task_id=task.id
    ):
        return
    await send_feedback_best_effort(
        callback.bot,
        task,
        f"🗑 {user_display} удалил(а) кастом #{task.id:03d} (не бриф)",
        event="not_task_confirm_feedback",
    )
    if not await safe_delete_message(callback, task.id):
        await callback.answer("Задача удалена, но сообщение не удалось удалить")
        return
    await callback.answer("Удалено")


async def action_not_task_cancel(callback, task, session, user, user_name, user_display):
    clear_delete_confirmation(user.id, task.id)
    card_refreshed = await refresh_card(callback, task)
    if not card_refreshed:
        await send_feedback(
            callback.bot,
            task,
            f"↩️ {user_display} отменил(а) удаление кастома #{task.id:03d}",
        )
    await callback.answer("Удаление отменено")
