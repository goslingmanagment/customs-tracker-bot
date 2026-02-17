import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.config import runtime
from core.permissions import get_role_cache, is_admin
from core.text_utils import esc, normalize_username
from db.engine import async_session
from db.models import RoleMembership
from db.repo import role_repo
from services.role_service import load_role_cache, resolve_admin_identity

logger = structlog.get_logger()

router = Router()


def _is_working_topic(message: Message) -> bool:
    return (
        message.chat.id == runtime.customs_chat_id
        and message.message_thread_id == runtime.customs_topic_id
    )


def _role_titles(role: str) -> tuple[str, str]:
    if role == "admin":
        return "👥 <b>Администраторы:</b>\n", "админ"
    if role == "model":
        return "👤 <b>Модели:</b>\n", "модель"
    return "🧭 <b>Тимлиды:</b>\n", "тимлид"


def _role_plural(role: str) -> str:
    if role == "admin":
        return "админов"
    if role == "model":
        return "моделей"
    return "тимлидов"


def _usage_message(role: str) -> str:
    if role == "admin":
        return (
            "📋 <b>Управление админами:</b>\n\n"
            "/admin list — список админов\n"
            "/admin add @username — добавить админа\n"
            "/admin add 123456789 — добавить по ID\n"
            "/admin add — добавить по reply на сообщение\n"
            "/admin remove @username — удалить админа\n"
            "/admin remove 123456789 — удалить по ID"
        )
    if role == "model":
        return (
            "📋 <b>Управление моделями:</b>\n\n"
            "/model list — список моделей\n"
            "/model add @username — добавить модель\n"
            "/model add 123456789 — добавить по ID\n"
            "/model add — добавить по reply на сообщение\n"
            "/model remove @username — удалить модель\n"
            "/model remove 123456789 — удалить по ID"
        )
    return (
        "📋 <b>Управление тимлидами:</b>\n\n"
        "/teamlead list — список тимлидов\n"
        "/teamlead add @username — добавить тимлида\n"
        "/teamlead add 123456789 — добавить по ID\n"
        "/teamlead add — добавить по reply на сообщение\n"
        "/teamlead remove @username — удалить тимлида\n"
        "/teamlead remove 123456789 — удалить по ID"
    )


def _topic_error(command_name: str) -> str:
    if runtime.customs_chat_id == 0 or runtime.customs_topic_id == 0:
        return "Бот ещё не привязан к топику. Выполните /setup в нужном топике."
    return (
        f"Команда /{command_name} работает только в рабочем топике "
        f"(chat: <code>{runtime.customs_chat_id}</code>, "
        f"topic: <code>{runtime.customs_topic_id}</code>)"
    )


def _role_manage_error(role: str) -> str:
    if role == "admin":
        return "Только администраторы могут управлять списком админов"
    if role == "model":
        return "Только администраторы могут управлять списком моделей"
    return "Только администраторы могут управлять списком тимлидов"


async def _role_list(message: Message, role: str):
    title, _ = _role_titles(role)

    async with async_session() as session:
        members = await role_repo.list_role_members(session, role)

    lines = [title.strip()]
    if members:
        for member in members:
            lines.append(f"• {_format_member_line(member)}")
    else:
        lines.append("Список пуст")

    await message.reply("\n".join(lines))


def _format_member_line(member: RoleMembership) -> str:
    username = normalize_username(member.username or "")
    has_username = bool(username)
    has_id = member.user_id is not None

    if has_username and has_id:
        return f"@{esc(username)} (ID: <code>{int(member.user_id)}</code>)"
    if has_username:
        return f"@{esc(username)}"
    if has_id:
        return f"ID: <code>{int(member.user_id)}</code>"
    return "—"


def _build_roles_overview_lines(
    admins: list[RoleMembership],
    models: list[RoleMembership],
    teamleads: list[RoleMembership],
) -> list[str]:
    sections = [
        ("admin", admins),
        ("model", models),
        ("teamlead", teamleads),
    ]
    lines = ["👥 <b>Роли</b>", ""]
    for role, members in sections:
        lines.append(_role_titles(role)[0].strip())
        if members:
            for member in members:
                lines.append(f"• {_format_member_line(member)}")
        else:
            lines.append("• Список пуст")
        lines.append("")
    if lines[-1] == "":
        lines.pop()
    return lines


async def _role_add(message: Message, role: str, value: str):
    role_ids, role_usernames = get_role_cache(role)
    _, role_label = _role_titles(role)
    role_plural = _role_plural(role)
    actor = message.from_user
    actor_id = actor.id if actor else None
    actor_name = actor.username or actor.full_name if actor else None

    if value.startswith("@"):
        username = normalize_username(value)
        if not username:
            await message.reply("Укажите юзернейм после @")
            return
        if username in {normalize_username(item) for item in role_usernames if item}:
            await message.reply(f"@{esc(username)} уже в списке {role_plural}")
            return

        async with async_session() as session:
            await role_repo.upsert_role_member(
                session, role, username=username,
                created_by_id=actor_id, created_by_name=actor_name,
            )
            await session.commit()
            await load_role_cache(session)

        logger.info(f"{role}_added_username", username=username, by=actor_id)
        await message.reply(
            f"✅ @{esc(username)} добавлен(а) как {role_label}\n"
            "ID будет привязан при первом действии"
        )
        return

    try:
        user_id = int(value)
    except ValueError:
        await message.reply("Укажите @username или числовой ID")
        return

    if user_id in role_ids:
        await message.reply(f"<code>{user_id}</code> уже в списке {role_plural}")
        return

    async with async_session() as session:
        await role_repo.upsert_role_member(
            session, role, user_id=user_id,
            created_by_id=actor_id, created_by_name=actor_name,
        )
        await session.commit()
        await load_role_cache(session)

    logger.info(f"{role}_added_id", user_id=user_id, by=actor_id)
    await message.reply(f"✅ <code>{user_id}</code> добавлен(а) как {role_label}")


async def _role_remove(message: Message, role: str, value: str):
    role_ids, role_usernames = get_role_cache(role)
    _, role_label = _role_titles(role)
    role_plural = _role_plural(role)
    actor = message.from_user
    actor_id = actor.id if actor else None

    if value.startswith("@"):
        username = normalize_username(value)
        if not username:
            await message.reply("Укажите юзернейм после @")
            return
        if username not in {normalize_username(item) for item in role_usernames if item}:
            await message.reply(f"@{esc(username)} не найден(а) в списке {role_plural}")
            return

        async with async_session() as session:
            await role_repo.remove_role_member(session, role, username=username)
            await session.commit()
            await load_role_cache(session)

        logger.info(f"{role}_removed_username", username=username, by=actor_id)
        await message.reply(f"❌ @{esc(username)} удалён(а) из {role_plural}")
        return

    try:
        user_id = int(value)
    except ValueError:
        await message.reply("Укажите @username или числовой ID")
        return

    if user_id not in role_ids:
        await message.reply(f"<code>{user_id}</code> не найден(а) в списке {role_plural}")
        return

    async with async_session() as session:
        await role_repo.remove_role_member(session, role, user_id=user_id)
        await session.commit()
        await load_role_cache(session)

    logger.info(f"{role}_removed_id", user_id=user_id, by=actor_id)
    await message.reply(f"❌ <code>{user_id}</code> удалён(а) из {role_plural}")


async def _handle_role_command(message: Message, role: str, command_name: str):
    if not _is_working_topic(message):
        await message.reply(_topic_error(command_name))
        return

    if not is_admin(message.from_user):
        await message.reply(_role_manage_error(role))
        return

    async with async_session() as session:
        await resolve_admin_identity(message.from_user, session)

    args = (message.text or "").split(maxsplit=2)
    if len(args) < 2:
        await message.reply(_usage_message(role))
        return

    action = args[1].lower()
    if action == "list":
        await _role_list(message, role)
    elif action == "add":
        if len(args) > 2:
            await _role_add(message, role, args[2].strip())
            return

        target_message = message.reply_to_message
        target_user = target_message.from_user if target_message else None
        if not target_user:
            await message.reply(_usage_message(role))
            return
        if target_user.is_bot:
            await message.reply("Нельзя добавить бота в роль")
            return
        await _role_add(message, role, str(target_user.id))
    elif action == "remove" and len(args) > 2:
        await _role_remove(message, role, args[2].strip())
    else:
        await message.reply(f"Использование: /{command_name} list | add | remove")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await _handle_role_command(message, "admin", "admin")


@router.message(Command("model"))
async def cmd_model(message: Message):
    await _handle_role_command(message, "model", "model")


@router.message(Command("teamlead"))
async def cmd_teamlead(message: Message):
    await _handle_role_command(message, "teamlead", "teamlead")


@router.message(Command("roles"))
async def cmd_roles(message: Message):
    if not _is_working_topic(message):
        await message.reply(_topic_error("roles"))
        return

    if not is_admin(message.from_user):
        await message.reply("Только администраторы могут просматривать список ролей")
        return

    async with async_session() as session:
        await resolve_admin_identity(message.from_user, session)
        admins = await role_repo.list_role_members(session, "admin")
        models = await role_repo.list_role_members(session, "model")
        teamleads = await role_repo.list_role_members(session, "teamlead")

    await message.reply(
        "\n".join(_build_roles_overview_lines(admins, models, teamleads))
    )
