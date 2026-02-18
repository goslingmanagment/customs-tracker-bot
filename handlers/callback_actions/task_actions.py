"""Task status and open-card callback actions."""

from core.exceptions import InvalidTransitionError
from db.repo import task_repo
from ui.cards import get_card_for_status
from ui.formatters import format_amount

from .common import (
    card_refresh_note,
    commit_session_safely,
    model_mentions,
    refresh_card,
    safe_delete_message,
    send_feedback,
    send_feedback_best_effort,
)


async def action_confirm_brief(callback, task, session, user, user_name, user_display):
    try:
        await task_repo.update_task_status(
            session, task, "awaiting_confirmation",
            changed_by_id=user.id, changed_by_name=user_name,
        )
    except InvalidTransitionError:
        if task.status == "awaiting_confirmation":
            await refresh_card(callback, task)
            await callback.answer("Бриф уже подтверждён ✅")
            return
        await callback.answer(f"Переход недоступен: {task.status} → awaiting_confirmation")
        return
    if not await commit_session_safely(
        session, callback, action="confirm_brief", task_id=task.id
    ):
        return
    card_refreshed = await refresh_card(callback, task)
    await callback.answer("Бриф подтверждён ✅")
    amount = format_amount(task.amount_total)
    feedback = f"✅ {user_display} подтвердил(а) кастом #{task.id:03d} ({amount})"
    if not card_refreshed:
        feedback += card_refresh_note(task.id)
    mentions = model_mentions()
    if mentions:
        feedback += f" — {mentions}"
    await send_feedback_best_effort(
        callback.bot,
        task,
        feedback,
        event="confirm_brief_feedback",
    )


async def action_take(callback, task, session, user, user_name, user_display):
    try:
        await task_repo.update_task_status(
            session, task, "processing",
            changed_by_id=user.id, changed_by_name=user_name,
        )
    except InvalidTransitionError:
        if task.status == "processing":
            await refresh_card(callback, task)
            await callback.answer("Кастом уже в работе 🎬")
            return
        await callback.answer(f"Переход недоступен: {task.status} → processing")
        return
    if not await commit_session_safely(
        session, callback, action="take", task_id=task.id
    ):
        return
    card_refreshed = await refresh_card(callback, task)
    await callback.answer("Взято в работу 🎬")
    amount = format_amount(task.amount_total)
    feedback = (
        f"🎬 {user_display} взяла в работу кастом #{task.id:03d} ({amount})"
    )
    if not card_refreshed:
        feedback += card_refresh_note(task.id)
    await send_feedback_best_effort(
        callback.bot,
        task,
        feedback,
        event="take_feedback",
    )


async def action_finish(callback, task, session, user, user_name, user_display):
    try:
        await task_repo.update_task_status(
            session, task, "finished",
            changed_by_id=user.id, changed_by_name=user_name,
        )
    except InvalidTransitionError:
        if task.status == "finished":
            await refresh_card(callback, task)
            await callback.answer("Кастом уже отмечен как отснятый 📹")
            return
        await callback.answer(f"Переход недоступен: {task.status} → finished")
        return
    if not await commit_session_safely(
        session, callback, action="finish", task_id=task.id
    ):
        return
    card_refreshed = await refresh_card(callback, task)
    await callback.answer("Отмечено как отснято 📹")
    feedback = (
        f"📹 {user_display} отметил(а) кастом #{task.id:03d} как отснято"
    )
    if not card_refreshed:
        feedback += card_refresh_note(task.id)
    await send_feedback_best_effort(
        callback.bot,
        task,
        feedback,
        event="finish_feedback",
    )


async def action_delivered(callback, task, session, user, user_name, user_display):
    try:
        await task_repo.update_task_status(
            session, task, "delivered",
            changed_by_id=user.id, changed_by_name=user_name,
        )
    except InvalidTransitionError:
        if task.status == "delivered":
            await refresh_card(callback, task)
            await callback.answer("Кастом уже отмечен как доставленный ✔️")
            return
        await callback.answer(f"Переход недоступен: {task.status} → delivered")
        return
    if not await commit_session_safely(
        session, callback, action="delivered", task_id=task.id
    ):
        return
    card_refreshed = await refresh_card(callback, task)
    await callback.answer("Доставлено ✔️")
    amount = format_amount(task.amount_total)
    feedback = (
        f"📤 {user_display} отметил(а) кастом #{task.id:03d} "
        f"как доставлено ({amount})"
    )
    if not card_refreshed:
        feedback += card_refresh_note(task.id)
    await send_feedback_best_effort(
        callback.bot,
        task,
        feedback,
        event="delivered_feedback",
    )


async def action_confirm_shot(callback, task, session, user, user_name, user_display):
    try:
        await task_repo.update_task_status(
            session, task, "finished",
            changed_by_id=user.id, changed_by_name=user_name,
        )
    except InvalidTransitionError:
        await callback.answer(f"Переход недоступен: {task.status} → finished")
        return
    if not await commit_session_safely(
        session, callback, action="confirm_shot", task_id=task.id
    ):
        return
    card_refreshed = await refresh_card(callback, task)
    await safe_delete_message(callback, task.id)
    await callback.answer("Отмечено как отснято 📹")
    feedback = f"📹 {user_display} подтвердил(а) съёмку кастома #{task.id:03d}"
    if not card_refreshed:
        feedback += card_refresh_note(task.id)
    await send_feedback_best_effort(
        callback.bot,
        task,
        feedback,
        event="confirm_shot_feedback",
    )


async def action_deny_shot(callback, task, session, user, user_name, user_display):
    if not await safe_delete_message(callback, task.id):
        await callback.answer("Не удалось удалить сообщение подтверждения")
        return
    await callback.answer("Ок, не отмечаем")


async def action_confirm_delivered(callback, task, session, user, user_name, user_display):
    try:
        await task_repo.update_task_status(
            session, task, "delivered",
            changed_by_id=user.id, changed_by_name=user_name,
        )
    except InvalidTransitionError:
        await callback.answer(f"Переход недоступен: {task.status} → delivered")
        return
    if not await commit_session_safely(
        session, callback, action="confirm_delivered", task_id=task.id
    ):
        return
    card_refreshed = await refresh_card(callback, task)
    await safe_delete_message(callback, task.id)
    await callback.answer("Доставлено ✔️")
    amount = format_amount(task.amount_total)
    feedback = (
        f"📤 {user_display} подтвердил(а) доставку кастома "
        f"#{task.id:03d} ({amount})"
    )
    if not card_refreshed:
        feedback += card_refresh_note(task.id)
    await send_feedback_best_effort(
        callback.bot,
        task,
        feedback,
        event="confirm_delivered_feedback",
    )


async def action_deny_delivered(callback, task, session, user, user_name, user_display):
    if not await safe_delete_message(callback, task.id):
        await callback.answer("Не удалось удалить сообщение подтверждения")
        return
    await callback.answer("Ок, не отмечаем")


async def action_open(callback, task, session, user, user_name, user_display):
    text, keyboard = get_card_for_status(task)
    await send_feedback(callback.bot, task, text, reply_markup=keyboard)
    await callback.answer(f"Открыт кастом #{task.id:03d}")
