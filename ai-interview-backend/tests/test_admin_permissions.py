from types import SimpleNamespace

import pytest

from app.api.backoffice.v1.admin import _can_manage_admins, _require_admin_manager, _require_root_admin
from app.models.admin import Admin, ROOT_ADMIN_EMAIL


def test_root_admin_email_is_stable():
    admin = Admin(email=ROOT_ADMIN_EMAIL)
    assert admin.is_root_admin is True


def test_can_manage_admins_uses_independent_permission_or_root():
    assert _can_manage_admins(SimpleNamespace(email="manager@example.com", can_manage_admins=True, is_root_admin=False))
    assert _can_manage_admins(SimpleNamespace(email=ROOT_ADMIN_EMAIL, can_manage_admins=False, is_root_admin=True))
    assert not _can_manage_admins(SimpleNamespace(email="admin@example.com", can_manage_admins=False, is_root_admin=False))


def test_permission_helpers_raise_403_for_unprivileged_admin():
    admin = SimpleNamespace(email="admin@example.com", can_manage_admins=False, is_root_admin=False)
    with pytest.raises(Exception) as manage_error:
        _require_admin_manager(admin)
    assert manage_error.value.status_code == 403

    with pytest.raises(Exception) as root_error:
        _require_root_admin(admin)
    assert root_error.value.status_code == 403
