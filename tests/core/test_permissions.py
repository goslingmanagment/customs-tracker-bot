from types import SimpleNamespace

from core.config import roles
from core.permissions import (
    can_add_brief,
    can_change_deadline,
    get_role_cache,
    is_admin,
    is_admin_or_model,
    is_admin_or_teamlead,
    is_detection_actor,
    is_model,
    is_teamlead,
)


def _user(user_id: int, username: str | None = None):
    return SimpleNamespace(id=user_id, username=username, full_name="User")


def test_role_checks_by_id():
    roles.admin_ids = [10]
    roles.model_ids = [20]
    roles.teamlead_ids = [30]

    assert is_admin(_user(10)) is True
    assert is_model(_user(20)) is True
    assert is_teamlead(_user(30)) is True


def test_role_checks_by_username_normalized():
    roles.admin_ids = []
    roles.admin_usernames = ["AdminUser"]

    assert is_admin(_user(999, "@adminuser")) is True
    assert is_admin(_user(999, "someone")) is False


def test_combined_permission_helpers():
    roles.admin_ids = [1]
    roles.model_ids = [2]
    roles.teamlead_ids = [3]

    assert is_admin_or_model(_user(1))
    assert is_admin_or_model(_user(2))
    assert is_admin_or_teamlead(_user(3))
    assert can_add_brief(_user(3))
    assert can_change_deadline(_user(2))
    assert is_detection_actor(_user(3))
    assert is_detection_actor(_user(2))
    assert is_detection_actor(_user(999)) is False


def test_get_role_cache():
    roles.admin_ids = [1]
    roles.admin_usernames = ["admin"]

    ids, usernames = get_role_cache("admin")
    assert ids == [1]
    assert usernames == ["admin"]
    assert get_role_cache("unknown") == ([], [])
