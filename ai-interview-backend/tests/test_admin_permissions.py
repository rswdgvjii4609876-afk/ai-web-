from types import SimpleNamespace
import asyncio

import pytest

from app.api.backoffice.deps import _has_admin_permission
from app.api.backoffice.v1.admin import _can_manage_admins, _require_admin_manager, _require_root_admin
from app.core.security import AuthBase
from app.models.admin import Admin, ROOT_ADMIN_EMAIL
from app.services.backoffice.auth import BackofficeAuthService


def test_root_admin_email_is_stable():
    admin = Admin(email=ROOT_ADMIN_EMAIL)
    assert admin.is_root_admin is True


def test_can_manage_admins_uses_independent_permission_or_root():
    assert _can_manage_admins(SimpleNamespace(email="manager@example.com", can_manage_admins=True, is_root_admin=False))
    assert _can_manage_admins(SimpleNamespace(email=ROOT_ADMIN_EMAIL, can_manage_admins=False, is_root_admin=True))
    assert not _can_manage_admins(SimpleNamespace(email="admin@example.com", can_manage_admins=False, is_root_admin=False))


def test_sensitive_backoffice_permissions_allow_root_or_explicit_grant():
    root = SimpleNamespace(email=ROOT_ADMIN_EMAIL, is_root_admin=True, can_review_cases=False)
    reviewer = SimpleNamespace(email="reviewer@example.com", is_root_admin=False, can_review_cases=True)
    regular = SimpleNamespace(email="admin@example.com", is_root_admin=False, can_review_cases=False)

    assert _has_admin_permission(root, "can_review_cases") is True
    assert _has_admin_permission(reviewer, "can_review_cases") is True
    assert _has_admin_permission(regular, "can_review_cases") is False


def test_permission_helpers_raise_403_for_unprivileged_admin():
    admin = SimpleNamespace(email="admin@example.com", can_manage_admins=False, is_root_admin=False)
    with pytest.raises(Exception) as manage_error:
        _require_admin_manager(admin)
    assert manage_error.value.status_code == 403

    with pytest.raises(Exception) as root_error:
        _require_root_admin(admin)
    assert root_error.value.status_code == 403


def test_backoffice_logout_accepts_refresh_scope_and_revokes_token():
    refresh_token = AuthBase.create_refresh_token("7")
    stored = SimpleNamespace(
        token=AuthBase.hash_refresh_token(refresh_token),
        is_active=True,
    )

    class _Result:
        def scalar_one_or_none(self):
            return stored

    class _Db:
        def __init__(self):
            self.committed = False

        async def execute(self, query):
            return _Result()

        async def commit(self):
            self.committed = True

    db = _Db()
    asyncio.run(BackofficeAuthService.logout(db, refresh_token))

    assert stored.is_active is False
    assert db.committed is True
