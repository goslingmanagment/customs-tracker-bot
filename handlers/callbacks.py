"""Inline button callback dispatcher for task actions."""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from core.text_utils import user_display_name
from db.engine import async_session
from db.repo import task_repo
from handlers.callback_actions.common import (
    commit_session_safely,
    denied_message,
    is_allowed,
    parse_callback,
)
from handlers.callback_actions.delete_actions import (
    action_not_task,
    action_not_task_cancel,
    action_not_task_confirm,
)
from handlers.callback_actions.postpone_actions import (
    action_cancel_postpone,
    action_postpone,
    action_postpone_1d,
    action_postpone_3d,
    action_postpone_7d,
)
from handlers.callback_actions.task_actions import (
    action_confirm_brief,
    action_confirm_delivered,
    action_confirm_shot,
    action_delivered,
    action_deny_delivered,
    action_deny_shot,
    action_finish,
    action_open,
    action_take,
)
from services.role_service import resolve_known_roles

router = Router()

ACTION_HANDLERS = {
    "confirm_brief": action_confirm_brief,
    "not_task": action_not_task,
    "not_task_confirm": action_not_task_confirm,
    "not_task_cancel": action_not_task_cancel,
    "take": action_take,
    "finish": action_finish,
    "delivered": action_delivered,
    "postpone": action_postpone,
    "postpone_1d": action_postpone_1d,
    "postpone_3d": action_postpone_3d,
    "postpone_7d": action_postpone_7d,
    "cancel_postpone": action_cancel_postpone,
    "confirm_shot": action_confirm_shot,
    "deny_shot": action_deny_shot,
    "confirm_delivered": action_confirm_delivered,
    "deny_delivered": action_deny_delivered,
    "open": action_open,
}


@router.callback_query(F.data.startswith("task:"))
async def handle_task_callback(callback: CallbackQuery):
    parsed = parse_callback(callback.data)
    if not parsed:
        await callback.answer("Ошибка: неверные данные")
        return

    task_id, action = parsed
    user = callback.from_user
    user_name = user.username or user.full_name
    user_display = user_display_name(user)

    if not is_allowed(action, user):
        await callback.answer(denied_message(action))
        return

    handler_fn = ACTION_HANDLERS.get(action)
    if not handler_fn:
        await callback.answer("Неизвестное действие")
        return

    async with async_session() as session:
        await resolve_known_roles(user, session)

        task = await task_repo.get_task_by_id(session, task_id)
        if not task:
            await callback.answer("Задача не найдена")
            return

        if callback.message and callback.message.chat.id != task.chat_id:
            await callback.answer("Действие недоступно")
            return
        if callback.message and callback.message.message_thread_id != task.topic_id:
            await callback.answer("Действие недоступно")
            return

        await handler_fn(callback, task, session, user, user_name, user_display)
        if session.new or session.dirty or session.deleted:
            if not await commit_session_safely(
                session,
                callback,
                action=f"fallback:{action}",
                task_id=task_id,
            ):
                return
