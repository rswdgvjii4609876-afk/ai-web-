import base64
import hashlib
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.exceptions.http_exceptions import ValidationError
from app.models.user import User


class DeepSeekConfigService:
    SUPPORTED_PROVIDERS = {"deepseek", "openai"}

    @staticmethod
    def _normalized_secret() -> str:
        secret = (settings.USER_LLM_CREDENTIAL_SECRET or "").strip()
        return secret or settings.SECRET_KEY

    @staticmethod
    def _cipher() -> Fernet:
        digest = hashlib.sha256(
            DeepSeekConfigService._normalized_secret().encode("utf-8")
        ).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    @staticmethod
    def encrypt_api_key(api_key: str) -> str:
        cleaned = (api_key or "").strip()
        if not cleaned:
            raise ValidationError(message="DeepSeek API Key 不能为空")
        return DeepSeekConfigService._cipher().encrypt(cleaned.encode("utf-8")).decode("utf-8")

    @staticmethod
    def decrypt_api_key(payload: Optional[str]) -> Optional[str]:
        if not payload:
            return None
        try:
            return DeepSeekConfigService._cipher().decrypt(payload.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError, TypeError):
            return None

    @staticmethod
    def normalize_provider(provider: Optional[str]) -> str:
        normalized = (provider or "").strip().lower() or "deepseek"
        if normalized not in DeepSeekConfigService.SUPPORTED_PROVIDERS:
            raise ValidationError(message="暂不支持所选 AI 服务商")
        return normalized

    @staticmethod
    def provider_label(provider: Optional[str]) -> str:
        normalized = DeepSeekConfigService.normalize_provider(provider)
        return "ChatGPT / OpenAI" if normalized == "openai" else "DeepSeek"

    @staticmethod
    def _provider_field_names(provider: str) -> Dict[str, str]:
        normalized = DeepSeekConfigService.normalize_provider(provider)
        if normalized == "openai":
            return {
                "key": "openai_api_key_encrypted",
                "base_url": "openai_base_url",
                "model": "openai_model",
            }
        return {
            "key": "deepseek_api_key_encrypted",
            "base_url": "deepseek_base_url",
            "model": "deepseek_model",
        }

    @staticmethod
    def default_base_url(provider: Optional[str]) -> str:
        normalized = DeepSeekConfigService.normalize_provider(provider)
        if normalized == "openai":
            return settings.OPENAI_BASE_URL
        return settings.DEEPSEEK_BASE_URL

    @staticmethod
    def default_model(provider: Optional[str]) -> str:
        normalized = DeepSeekConfigService.normalize_provider(provider)
        if normalized == "openai":
            return settings.OPENAI_MODEL
        return settings.DEEPSEEK_MODEL

    @staticmethod
    def summarize_for_profile(user: User) -> Dict:
        selected_provider = DeepSeekConfigService.normalize_provider(
            getattr(user, "ai_provider", None)
        )
        has_deepseek_key = bool(getattr(user, "deepseek_api_key_encrypted", None))
        has_openai_key = bool(getattr(user, "openai_api_key_encrypted", None))
        return {
            "ai_provider": selected_provider,
            "deepseek_use_personal_api": selected_provider == "deepseek" and has_deepseek_key,
            "deepseek_has_personal_api_key": has_deepseek_key,
            "deepseek_base_url": getattr(user, "deepseek_base_url", None) or settings.DEEPSEEK_BASE_URL,
            "deepseek_model": getattr(user, "deepseek_model", None) or settings.DEEPSEEK_MODEL,
            "openai_has_personal_api_key": has_openai_key,
            "openai_base_url": getattr(user, "openai_base_url", None) or settings.OPENAI_BASE_URL,
            "openai_model": getattr(user, "openai_model", None) or settings.OPENAI_MODEL,
        }

    @staticmethod
    def build_runtime_config(
        user: Optional[User],
        require_personal_key: bool = False,
        provider: Optional[str] = None,
    ) -> Optional[Dict]:
        if not user:
            if require_personal_key:
                raise ValidationError(message="请先登录后再使用 AI 功能")
            return None

        provider = DeepSeekConfigService.normalize_provider(
            provider or getattr(user, "ai_provider", None)
        )
        field_names = DeepSeekConfigService._provider_field_names(provider)
        provider_label = DeepSeekConfigService.provider_label(provider)
        encrypted_key = getattr(user, field_names["key"], None)
        if not encrypted_key:
            if require_personal_key:
                raise ValidationError(
                    message=f"请先在个人中心保存你的 {provider_label} API Key"
                )
            return None

        api_key = DeepSeekConfigService.decrypt_api_key(encrypted_key)
        if not api_key:
            raise ValidationError(
                message=f"你的 {provider_label} API Key 无法读取，请在个人中心重新保存"
            )

        return {
            "provider": provider,
            "provider_label": provider_label,
            "source": f"user_{provider}",
            "api_key": api_key,
            "base_url": getattr(user, field_names["base_url"], None)
            or DeepSeekConfigService.default_base_url(provider),
            "model": getattr(user, field_names["model"], None)
            or DeepSeekConfigService.default_model(provider),
            "thinking": settings.DEEPSEEK_THINKING if provider == "deepseek" else None,
            "reasoning_effort": settings.DEEPSEEK_REASONING_EFFORT if provider == "deepseek" else None,
        }

    @staticmethod
    def build_embedding_candidates(user: Optional[User]) -> list[Dict]:
        if not user:
            return []

        candidates: list[Dict] = []
        deepseek_key = DeepSeekConfigService.decrypt_api_key(
            getattr(user, "deepseek_api_key_encrypted", None)
        )
        if deepseek_key:
            candidates.append(
                {
                    "provider": "deepseek",
                    "provider_label": "DeepSeek",
                    "api_key": deepseek_key,
                    "base_url": getattr(user, "deepseek_base_url", None)
                    or settings.DEEPSEEK_BASE_URL,
                    "model": settings.DEEPSEEK_EMBEDDING_MODEL,
                }
            )

        openai_key = DeepSeekConfigService.decrypt_api_key(
            getattr(user, "openai_api_key_encrypted", None)
        )
        if openai_key:
            candidates.append(
                {
                    "provider": "openai",
                    "provider_label": "OpenAI",
                    "api_key": openai_key,
                    "base_url": getattr(user, "openai_base_url", None)
                    or settings.OPENAI_BASE_URL,
                    "model": settings.OPENAI_EMBEDDING_MODEL,
                }
            )
        return candidates


deepseek_config_service = DeepSeekConfigService()
