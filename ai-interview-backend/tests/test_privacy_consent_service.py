from types import SimpleNamespace
import asyncio
import sys
import types

import pytest


def _install_redis_stub():
    if "redis.asyncio" in sys.modules:
        return
    redis_module = types.ModuleType("redis")
    redis_asyncio_module = types.ModuleType("redis.asyncio")

    class _Redis:
        def __init__(self, *args, **kwargs):
            pass

        async def setex(self, *args, **kwargs):
            return None

        async def get(self, *args, **kwargs):
            return None

        async def delete(self, *args, **kwargs):
            return None

        async def exists(self, *args, **kwargs):
            return False

        async def brpop(self, *args, **kwargs):
            return None

        async def close(self):
            return None

        def pipeline(self, *args, **kwargs):
            return self

    redis_asyncio_module.Redis = _Redis
    redis_module.asyncio = redis_asyncio_module
    sys.modules["redis"] = redis_module
    sys.modules["redis.asyncio"] = redis_asyncio_module


_install_redis_stub()

from app.constants.privacy import (
    BASE_PRIVACY_CONSENT_ERROR,
    DATA_CONTRIBUTION_CONSENT_VERSION,
    PRIVACY_POLICY_VERSION,
)
from app.api.client.deps import require_base_privacy_consent
from app.api.client.v1.auth import ProfileUpdate, _safe_avatar_extension, _serialize_user_profile, update_profile
from app.exceptions.http_exceptions import ValidationError
from app.services.client.auth import ClientAuthService
from app.services.client.privacy_consent_service import privacy_consent_service


def test_apply_base_consent_records_policy_version_and_time():
    user = SimpleNamespace(privacy_policy_version=None, privacy_agreed_at=None)

    privacy_consent_service.apply_base_consent(user, agreed=True)

    assert user.privacy_policy_version == PRIVACY_POLICY_VERSION
    assert user.privacy_agreed_at is not None


def test_base_consent_requires_current_policy_version():
    user = SimpleNamespace(
        privacy_policy_version="old-version",
        privacy_agreed_at="2026-05-15T00:00:00Z",
    )

    assert privacy_consent_service.has_base_consent(user) is False

    user.privacy_policy_version = PRIVACY_POLICY_VERSION
    assert privacy_consent_service.has_base_consent(user) is True


def test_base_privacy_dependency_rejects_missing_or_old_consent():
    user = SimpleNamespace(
        privacy_policy_version="old-version",
        privacy_agreed_at="2026-05-15T00:00:00Z",
    )

    async def _run():
        with pytest.raises(ValidationError) as exc:
            await require_base_privacy_consent(current_user=user)
        assert exc.value.detail == BASE_PRIVACY_CONSENT_ERROR

    asyncio.run(_run())


def test_data_contribution_consent_can_be_granted_and_withdrawn():
    user = SimpleNamespace(
        data_contribution_consent=False,
        data_contribution_consent_at=None,
        data_contribution_withdrawn_at=None,
        data_contribution_consent_version=None,
    )

    privacy_consent_service.set_data_contribution_consent(user, consent=True)

    assert user.data_contribution_consent is True
    assert user.data_contribution_consent_at is not None
    assert user.data_contribution_withdrawn_at is None
    assert user.data_contribution_consent_version == DATA_CONTRIBUTION_CONSENT_VERSION

    privacy_consent_service.set_data_contribution_consent(user, consent=False)

    assert user.data_contribution_consent is False
    assert user.data_contribution_withdrawn_at is not None


def test_data_contribution_consent_requires_current_version_for_default_use():
    user = SimpleNamespace(
        privacy_policy_version=PRIVACY_POLICY_VERSION,
        privacy_agreed_at="2026-05-15T00:00:00Z",
        data_contribution_consent=True,
        data_contribution_consent_version="old-version",
    )

    assert privacy_consent_service.has_data_contribution_consent(user) is False
    assert privacy_consent_service.effective_data_contribution_consent(user) is False
    assert privacy_consent_service.effective_data_contribution_consent(user, True) is True

    user.data_contribution_consent_version = DATA_CONTRIBUTION_CONSENT_VERSION
    assert privacy_consent_service.has_data_contribution_consent(user) is True
    assert privacy_consent_service.effective_data_contribution_consent(user) is True


def test_data_contribution_consent_requires_current_base_consent():
    user = SimpleNamespace(
        privacy_policy_version=None,
        privacy_agreed_at=None,
        data_contribution_consent=True,
        data_contribution_consent_version=DATA_CONTRIBUTION_CONSENT_VERSION,
    )

    assert privacy_consent_service.has_data_contribution_consent(user) is False
    assert privacy_consent_service.effective_data_contribution_consent(user) is False


def test_avatar_extension_rejects_svg_and_spoofed_images():
    assert _safe_avatar_extension("image/svg+xml", b"<svg></svg>") is None
    assert _safe_avatar_extension("image/png", b"<svg></svg>") is None
    assert _safe_avatar_extension("image/png", b"\x89PNG\r\n\x1a\nrest") == "png"
    assert _safe_avatar_extension("image/webp", b"RIFFxxxxWEBPrest") == "webp"


def test_snapshot_uses_deidentified_contribution_language():
    user = SimpleNamespace(
        privacy_policy_version=PRIVACY_POLICY_VERSION,
        privacy_agreed_at=None,
    )

    snapshot = privacy_consent_service.build_snapshot(
        user,
        data_contribution_consent=True,
        source="resume_upload",
    )

    assert snapshot["data_contribution_consent"] is True
    assert snapshot["source"] == "resume_upload"
    assert "去除或遮挡姓名、手机号、邮箱" in snapshot["deidentification_summary"]
    assert "学校、专业" in snapshot["deidentification_summary"]


def test_profile_cannot_enable_data_contribution_without_base_consent():
    user = SimpleNamespace(
        first_name="",
        last_name="",
        id=1,
        email="candidate@example.test",
        avatar=None,
        phone="",
        phone_country_code="+86",
        university="",
        career_goal="",
        contract_types=[],
        location="",
        gender="",
        is_verified=True,
        email_verified_at=None,
        last_active_at=None,
        ai_provider="deepseek",
        deepseek_api_key_encrypted="encrypted",
        openai_api_key_encrypted=None,
        deepseek_base_url=None,
        deepseek_model=None,
        openai_base_url=None,
        openai_model=None,
        deepseek_use_personal_api=True,
        privacy_policy_version=None,
        privacy_agreed_at=None,
        data_contribution_consent=False,
        data_contribution_consent_at=None,
        data_contribution_withdrawn_at=None,
        data_contribution_consent_version=None,
    )

    class _Db:
        async def commit(self):
            raise AssertionError("commit should not be called")

        async def refresh(self, item):
            return None

    async def _run():
        with pytest.raises(ValidationError) as exc:
            await update_profile(
                ProfileUpdate(data_contribution_consent=True),
                current_user=user,
                db=_Db(),
            )
        assert exc.value.detail == BASE_PRIVACY_CONSENT_ERROR
        assert user.data_contribution_consent is False

    asyncio.run(_run())


def test_profile_can_apply_base_and_data_contribution_together():
    user = SimpleNamespace(
        id=1,
        email="candidate@example.test",
        first_name="",
        last_name="",
        avatar=None,
        phone="",
        phone_country_code="+86",
        university="",
        career_goal="",
        contract_types=[],
        location="",
        gender="",
        is_verified=True,
        email_verified_at=None,
        last_active_at=None,
        ai_provider="deepseek",
        deepseek_api_key_encrypted="encrypted",
        openai_api_key_encrypted=None,
        deepseek_base_url=None,
        deepseek_model=None,
        openai_base_url=None,
        openai_model=None,
        deepseek_use_personal_api=True,
        privacy_policy_version=None,
        privacy_agreed_at=None,
        data_contribution_consent=False,
        data_contribution_consent_at=None,
        data_contribution_withdrawn_at=None,
        data_contribution_consent_version=None,
    )

    class _Db:
        async def commit(self):
            return None

        async def refresh(self, item):
            return None

    async def _run():
        await update_profile(
            ProfileUpdate(privacy_agreed=True, data_contribution_consent=True),
            current_user=user,
            db=_Db(),
        )
        assert privacy_consent_service.has_base_consent(user) is True
        assert user.data_contribution_consent is True

    asyncio.run(_run())


def test_profile_base_consent_does_not_revive_old_data_contribution():
    user = SimpleNamespace(
        id=1,
        email="candidate@example.test",
        first_name="",
        last_name="",
        avatar=None,
        phone="",
        phone_country_code="+86",
        university="",
        career_goal="",
        contract_types=[],
        location="",
        gender="",
        is_verified=True,
        email_verified_at=None,
        last_active_at=None,
        ai_provider="deepseek",
        deepseek_api_key_encrypted="encrypted",
        openai_api_key_encrypted=None,
        deepseek_base_url=None,
        deepseek_model=None,
        openai_base_url=None,
        openai_model=None,
        deepseek_use_personal_api=True,
        privacy_policy_version=None,
        privacy_agreed_at=None,
        data_contribution_consent=True,
        data_contribution_consent_at=None,
        data_contribution_withdrawn_at=None,
        data_contribution_consent_version=DATA_CONTRIBUTION_CONSENT_VERSION,
    )

    class _Db:
        async def commit(self):
            return None

        async def refresh(self, item):
            return None

    async def _run():
        await update_profile(
            ProfileUpdate(privacy_agreed=True),
            current_user=user,
            db=_Db(),
        )
        assert privacy_consent_service.has_base_consent(user) is True
        assert user.data_contribution_consent is False
        profile = _serialize_user_profile(user)
        assert profile["data_contribution_consent"] is False
        assert profile["data_contribution_consent_valid"] is False

    asyncio.run(_run())


def test_auth_response_reports_only_valid_data_contribution():
    user = SimpleNamespace(
        id=1,
        email="candidate@example.test",
        first_name="",
        last_name="",
        is_verified=True,
        university="",
        career_goal="",
        location="",
        privacy_policy_version=None,
        privacy_agreed_at=None,
        data_contribution_consent=True,
        data_contribution_consent_at=None,
        data_contribution_withdrawn_at=None,
        data_contribution_consent_version=DATA_CONTRIBUTION_CONSENT_VERSION,
    )

    response = ClientAuthService._build_auth_response(user, "access", "refresh")

    assert response["user"]["data_contribution_consent"] is False
    assert response["user"]["data_contribution_consent_valid"] is False
