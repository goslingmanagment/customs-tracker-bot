"""All role-checking logic in one place. Reads from core.config.roles."""

from aiogram.types import User

from core.config import roles
from core.text_utils import normalize_username


def _username_in_cache(cache_usernames: list[str], username: str | None) -> bool:
    normalized = normalize_username(username)
    if not normalized:
        return False
    return normalized in {normalize_username(u) for u in cache_usernames if u}


def is_admin(user: User | None) -> bool:
    if not user:
        return False
    if roles.admin_ids and user.id in roles.admin_ids:
        return True
    if roles.admin_usernames:
        return _username_in_cache(roles.admin_usernames, user.username)
    return False


def is_model(user: User | None) -> bool:
    if not user:
        return False
    if roles.model_ids and user.id in roles.model_ids:
        return True
    if roles.model_usernames:
        return _username_in_cache(roles.model_usernames, user.username)
    return False


def is_teamlead(user: User | None) -> bool:
    if not user:
        return False
    if roles.teamlead_ids and user.id in roles.teamlead_ids:
        return True
    if roles.teamlead_usernames:
        return _username_in_cache(roles.teamlead_usernames, user.username)
    return False


def is_admin_or_model(user: User | None) -> bool:
    return is_admin(user) or is_model(user)


def is_admin_or_teamlead(user: User | None) -> bool:
    return is_admin(user) or is_teamlead(user)


def can_add_brief(user: User | None) -> bool:
    return is_admin(user) or is_model(user) or is_teamlead(user)


def can_change_deadline(user: User | None) -> bool:
    return is_admin(user) or is_teamlead(user) or is_model(user)


def is_detection_actor(user: User | None) -> bool:
    """Can trigger shot/delivery detection prompts."""
    return is_admin_or_teamlead(user) or is_model(user)


def get_role_cache(role: str) -> tuple[list[int], list[str]]:
    if role == "admin":
        return roles.admin_ids, roles.admin_usernames
    if role == "model":
        return roles.model_ids, roles.model_usernames
    if role == "teamlead":
        return roles.teamlead_ids, roles.teamlead_usernames
    return [], []
