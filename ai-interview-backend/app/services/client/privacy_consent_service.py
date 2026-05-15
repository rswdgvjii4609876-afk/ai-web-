from datetime import UTC, datetime
from typing import Any, Dict, Optional

from app.constants.privacy import (
    DATA_CONTRIBUTION_CONSENT_VERSION,
    DATA_CONTRIBUTION_DEIDENTIFICATION_SUMMARY,
    PRIVACY_POLICY_VERSION,
)
from app.models.user import User


class PrivacyConsentService:
    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def has_base_consent(user: User) -> bool:
        return bool(getattr(user, "privacy_agreed_at", None))

    @staticmethod
    def apply_base_consent(user: User, *, agreed: bool) -> None:
        if not agreed:
            return
        user.privacy_policy_version = PRIVACY_POLICY_VERSION
        user.privacy_agreed_at = PrivacyConsentService.now()

    @staticmethod
    def set_data_contribution_consent(user: User, *, consent: bool) -> None:
        user.data_contribution_consent = bool(consent)
        user.data_contribution_consent_version = DATA_CONTRIBUTION_CONSENT_VERSION
        if consent:
            user.data_contribution_consent_at = PrivacyConsentService.now()
            user.data_contribution_withdrawn_at = None
        else:
            user.data_contribution_withdrawn_at = PrivacyConsentService.now()

    @staticmethod
    def effective_data_contribution_consent(
        user: User,
        explicit_consent: Optional[bool] = None,
    ) -> bool:
        if explicit_consent is not None:
            return bool(explicit_consent)
        return bool(getattr(user, "data_contribution_consent", False))

    @staticmethod
    def build_snapshot(
        user: User,
        *,
        data_contribution_consent: bool,
        source: str,
    ) -> Dict[str, Any]:
        return {
            "privacy_policy_version": getattr(user, "privacy_policy_version", None),
            "privacy_agreed_at": (
                user.privacy_agreed_at.isoformat()
                if getattr(user, "privacy_agreed_at", None)
                else None
            ),
            "data_contribution_consent": bool(data_contribution_consent),
            "data_contribution_consent_version": (
                DATA_CONTRIBUTION_CONSENT_VERSION if data_contribution_consent else None
            ),
            "captured_at": PrivacyConsentService.now().isoformat(),
            "source": source,
            "deidentification_summary": DATA_CONTRIBUTION_DEIDENTIFICATION_SUMMARY,
        }


privacy_consent_service = PrivacyConsentService()
