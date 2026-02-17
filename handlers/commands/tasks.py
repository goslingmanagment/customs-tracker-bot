import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.permissions import is_admin
from core.text_utils import esc
from db.engine import async_session
from db.repo import task_repo
from handlers.filters import WorkingTopicFilter
from services.role_service import resolve_admin_identity
from ui.cards import get_card_for_status
from ui.formatters import (
    PRIORITY_EMOJI,
    STATUS_EMOJI,
    STATUS_LABEL,
    format_amount,
    format_days_overdue,
    format_deadline_status,
)

logger = structlog.get_logger()

router = Router()

REVERT_PREVIOUS_STATUS = {
    "awaiting_confirmation": "draft",
    "processing": "awaiting_confirmation",
    "finished": "processing",
    "delivered": "finished",
}


def _status_jump_keyboard(tasks) -> InlineKeyboardMarkup | None:
    if not tasks:
        return None
    buttons = [
        InlineKeyboardButton(
            text=f"{STATUS_EMOJI.get(task.status, '📌')} #{task.id:03d}",
            callback_data=f"task:{task.id}:open",
        )
        for task in tasks[:12]
    ]
    rows = [buttons[idx:idx + 3] for idx in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _refresh_task_card(message: Message, task) -> bool:
    if not task.bot_message_id:
        return False
    card_text, keyboard = get_card_for_status(task)
    try:
        await message.bot.edit_message_text(
            card_text,
            chat_id=task.chat_id,
            message_id=task.bot_message_id,
            reply_markup=keyboard,
        )
        return True
    except Exception as exc:
        logger.error("card_update_failed", task_id=task.id, error=str(exc))
        return False


@router.message(Command("status"), WorkingTopicFilter())
async def cmd_status(message: Message):
    async with async_session() as session:
        overdue = await task_repo.get_overdue_tasks(session)
        due_soon = await task_repo.get_tasks_due_soon(session, days=3)
        active = await task_repo.get_active_tasks(session)
        drafts = [t for t in active if t.status == "draft"]
        awaiting = [t for t in active if t.status == "awaiting_confirmation"]
        processing = [t for t in active if t.status == "processing"]
        finished = [t for t in active if t.status == "finished"]

        lines = ["📋 <b>Кастомы — Сводка</b>\n"]

        if overdue:
            lines.append(f"🔴 <b>Просрочено: {len(overdue)}</b>")
            for t in overdue[:5]:
                days = format_days_overdue(t.deadline)
                lines.append(
                    f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
                    f"{esc((t.description or '—')[:40])} | {days}"
                )
            lines.append("")

        if due_soon:
            lines.append(f"🟡 <b>Скоро дедлайн (3 дня): {len(due_soon)}</b>")
            for t in due_soon[:5]:
                lines.append(
                    f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
                    f"{format_deadline_status(t.deadline)}"
                )
            lines.append("")

        if drafts:
            lines.append(f"📋 <b>Черновики: {len(drafts)}</b>")
            for t in drafts[:5]:
                lines.append(
                    f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
                    f"{esc((t.description or '—')[:40])}"
                )
            lines.append("")

        if awaiting:
            lines.append(f"📦 <b>Ожидают модель: {len(awaiting)}</b>")
            for t in awaiting[:5]:
                lines.append(
                    f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
                    f"{esc((t.description or '—')[:40])}"
                )
            lines.append("")

        if processing:
            lines.append(f"🎬 <b>В работе: {len(processing)}</b>")
            for t in processing[:10]:
                lines.append(
                    f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
                    f"{esc((t.description or '—')[:40])} | {format_deadline_status(t.deadline)}"
                )
            lines.append("")

        if finished:
            lines.append(f"📹 <b>Отснято, не доставлено: {len(finished)}</b>")
            for t in finished[:10]:
                lines.append(
                    f"  #{t.id:03d} | {format_amount(t.amount_total)} | "
                    f"{esc((t.description or '—')[:40])}"
                )
            lines.append("")

        total_amount = sum(t.amount_total or 0 for t in active)
        lines.append(f"📊 Всего активных: {len(active)} | Сумма: ${total_amount:.0f}")

        if not any([overdue, due_soon, drafts, awaiting, processing, finished]):
            lines.append("\n✨ Нет активных кастомов")

        keyboard = _status_jump_keyboard(active)
        await message.reply("\n".join(lines), reply_markup=keyboard)


@router.message(Command("list"), WorkingTopicFilter())
async def cmd_list(message: Message):
    args = (message.text or "").split(maxsplit=1)
    filter_type = args[1].strip().lower() if len(args) > 1 else "active"

    async with async_session() as session:
        if filter_type == "all":
            tasks = await task_repo.get_all_tasks(session)
            title = "Все кастомы"
        elif filter_type == "active":
            tasks = await task_repo.get_active_tasks(session)
            title = "Активные"
        elif filter_type == "overdue":
            tasks = await task_repo.get_overdue_tasks(session)
            title = "Просроченные"
        elif filter_type == "draft":
            tasks = await task_repo.get_tasks_by_status(session, "draft")
            title = "Черновики"
        elif filter_type == "awaiting":
            tasks = await task_repo.get_tasks_by_status(session, "awaiting_confirmation")
            title = "Ожидают модель"
        elif filter_type == "processing":
            tasks = await task_repo.get_tasks_by_status(session, "processing")
            title = "В работе"
        elif filter_type == "finished":
            tasks = await task_repo.get_tasks_by_status(session, "finished")
            title = "Отснятые"
        elif filter_type == "delivered":
            tasks = await task_repo.get_tasks_by_status(session, "delivered")
            title = "Выполненные"
        else:
            tasks = await task_repo.get_active_tasks(session)
            title = "Активные"

        if not tasks:
            await message.reply(f"📋 {title}: пусто")
            return

        lines = [f"📋 <b>{title}: {len(tasks)}</b>\n"]
        for t in tasks[:20]:
            status_e = STATUS_EMOJI.get(t.status, "")
            priority_e = PRIORITY_EMOJI.get(t.priority, "")
            deadline = format_deadline_status(t.deadline)
            lines.append(
                f"{status_e} #{t.id:03d} | {format_amount(t.amount_total)} | "
                f"{esc((t.description or '—')[:35])} | {deadline} {priority_e}"
            )

        if len(tasks) > 20:
            lines.append(f"\n... и ещё {len(tasks) - 20}")

        await message.reply("\n".join(lines))


@router.message(Command("task"), WorkingTopicFilter())
async def cmd_task(message: Message):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Использование: /task {номер}")
        return

    try:
        task_id = int(args[1].strip().lstrip("#"))
    except ValueError:
        await message.reply("Номер задачи должен быть числом")
        return

    async with async_session() as session:
        task = await task_repo.get_task_by_id(session, task_id)
        if not task:
            await message.reply(f"Задача #{task_id} не найдена")
            return

        status_label = STATUS_LABEL.get(task.status, task.status)
        status_emoji = STATUS_EMOJI.get(task.status, "")
        priority_emoji = PRIORITY_EMOJI.get(task.priority, "")

        lines = [
            f"📦 <b>Кастом #{task.id:03d}</b>\n",
            f"📅 Дата: {esc(task.task_date) or '—'}",
        ]
        if task.fan_link:
            platform = esc((task.platform or "").capitalize())
            lines.append(f"👤 Фан: {esc(task.fan_name) or '—'} ({platform})")
            lines.append(f"🔗 {esc(task.fan_link)}")
        elif task.fan_name:
            lines.append(f"👤 Фан: {esc(task.fan_name)}")

        lines.append(f"💰 Сумма: {format_amount(task.amount_total, task.payment_note)}")
        if task.duration:
            lines.append(f"⏱ Длительность: {esc(task.duration)}")
        if task.description:
            lines.append(f"🎬 Описание: {esc(task.description)}")
        if task.outfit:
            lines.append(f"👗 Одежда: {esc(task.outfit)}")
        if task.notes:
            lines.append(f"📝 Заметки: {esc(task.notes)}")
        lines.append(f"🔥 Срочность: {priority_emoji} {esc(task.priority)}")
        lines.append(f"📅 Дедлайн: {format_deadline_status(task.deadline) if task.deadline else '—'}")
        lines.append(f"Статус: {status_emoji} {status_label}")

        text = "\n".join(lines)
        _, keyboard = get_card_for_status(task)
        await message.reply(text, reply_markup=keyboard)


@router.message(Command("revert"), WorkingTopicFilter())
async def cmd_revert(message: Message):
    if not is_admin(message.from_user):
        await message.reply("Доступно только администраторам")
        return

    async with async_session() as session:
        await resolve_admin_identity(message.from_user, session)

    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Использование: /revert {номер}")
        return

    try:
        task_id = int(args[1].strip().lstrip("#"))
    except ValueError:
        await message.reply("Номер задачи должен быть числом")
        return

    actor = message.from_user
    actor_name = actor.username or actor.full_name if actor else None
    actor_id = actor.id if actor else None

    async with async_session() as session:
        task = await task_repo.get_task_by_id(session, task_id)
        if not task:
            await message.reply(f"Задача #{task_id} не найдена")
            return

        previous_status = REVERT_PREVIOUS_STATUS.get(task.status)
        if not previous_status:
            await message.reply(
                f"Кастом #{task.id:03d} в статусе {task.status} нельзя откатить назад"
            )
            return

        current_status = task.status
        await task_repo.force_update_task_status(
            session,
            task,
            previous_status,
            changed_by_id=actor_id,
            changed_by_name=actor_name,
            note="manual_revert_command",
        )
        await session.commit()

        card_refreshed = await _refresh_task_card(message, task)

    result = (
        f"↩️ Кастом #{task_id:03d} возвращён назад: "
        f"{current_status} → {previous_status}"
    )
    if not card_refreshed:
        result += (
            f"\n⚠️ Карточку не удалось обновить автоматически. "
            f"Откройте /task {task_id}."
        )
    await message.reply(result)
