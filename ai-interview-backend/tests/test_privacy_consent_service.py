from types import SimpleNamespace

from app.constants.privacy import (
    DATA_CONTRIBUTION_CONSENT_VERSION,
    PRIVACY_POLICY_VERSION,
)
from app.services.client.privacy_consent_service import privacy_consent_service


def test_apply_base_consent_records_policy_version_and_time():
    user = SimpleNamespace(privacy_policy_version=None, privacy_agreed_at=None)

    privacy_consent_service.apply_base_consent(user, agreed=True)

    assert user.privacy_policy_version == PRIVACY_POLICY_VERSION
    assert user.privacy_agreed_at is not None


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
