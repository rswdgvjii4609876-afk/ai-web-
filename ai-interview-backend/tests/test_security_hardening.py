import sys
import types

import pytest

from app.api.backoffice.deps import require_content_manager_admin
from app.api.client.v1.resume import _build_runtime_options, _validate_pdf_upload
from app.core.config import settings
from app.exceptions.http_exceptions import ValidationError
from app.schemas.client.auth import Login, ResetPassword, UserRegister
from app.services.client.output_safety_service import output_safety_service
from app.services.client.training_sample_export_service import training_sample_export_service
from app.services.common.deepseek_config_service import DeepSeekConfigService


@pytest.mark.unit
def test_reset_password_uses_pydantic_v2_model_validator():
    payload = ResetPassword(
        reset_token="token",
        new_password="Strong#123",
        confirm_password="Strong#123",
    )

    assert payload.new_password == "Strong#123"

    with pytest.raises(ValueError, match="确认密码"):
        ResetPassword(
            reset_token="token",
            new_password="Strong#123",
            confirm_password="Wrong#123",
        )


@pytest.mark.unit
def test_account_email_schemas_normalize_case_and_spaces():
    assert Login(email="  USER@Example.COM ", password="x").email == "user@example.com"
    assert UserRegister(
        first_name="A",
        last_name="B",
        email="  USER@Example.COM ",
        password="Strong#123",
        privacy_agreed=True,
    ).email == "user@example.com"


@pytest.mark.unit
def test_user_llm_base_url_guard_blocks_ssrf_and_requires_allowlist(monkeypatch):
    assert (
        DeepSeekConfigService.normalize_base_url("openai", "https://api.openai.com/v1/")
        == "https://api.openai.com/v1"
    )

    with pytest.raises(ValidationError, match="HTTPS"):
        DeepSeekConfigService.normalize_base_url("openai", "http://api.openai.com/v1")

    with pytest.raises(ValidationError, match="允许列表"):
        DeepSeekConfigService.normalize_base_url("deepseek", "https://relay.example.com/v1")

    monkeypatch.setattr(settings, "USER_LLM_ALLOWED_BASE_URLS", "https://127.0.0.1/v1")
    with pytest.raises(ValidationError, match="内网"):
        DeepSeekConfigService.normalize_base_url("deepseek", "https://127.0.0.1/v1")

    monkeypatch.setattr(settings, "USER_LLM_ALLOWED_BASE_URLS", "https://gateway.example.com/v1")
    monkeypatch.setattr(DeepSeekConfigService, "_is_private_or_reserved_host", staticmethod(lambda host: False))
    assert (
        DeepSeekConfigService.normalize_base_url("deepseek", "https://gateway.example.com/v1/")
        == "https://gateway.example.com/v1"
    )


@pytest.mark.unit
def test_resume_runtime_options_do_not_include_secrets():
    runtime_options = _build_runtime_options(
        {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "api_key": "sk-secret",
            "base_url": "https://api.deepseek.com",
        }
    )

    assert runtime_options == {"provider": "deepseek", "model": "deepseek-v4-pro"}
    assert "api_key" not in runtime_options
    assert "base_url" not in runtime_options


@pytest.mark.unit
def test_resume_pdf_upload_checks_magic_bytes_and_page_count(monkeypatch):
    class _PdfReader:
        def __init__(self, content, strict=False):
            self.pages = [object()]

    module = types.ModuleType("PyPDF2")
    module.PdfReader = _PdfReader
    monkeypatch.setitem(sys.modules, "PyPDF2", module)

    valid_pdf = b"%PDF-1.4\nfake body"
    _validate_pdf_upload(valid_pdf, "application/pdf")

    with pytest.raises(ValidationError, match="PDF"):
        _validate_pdf_upload(b"not a pdf", "application/pdf")

    with pytest.raises(ValidationError, match="PDF"):
        _validate_pdf_upload(valid_pdf, "text/plain")


@pytest.mark.unit
def test_output_safety_blocks_internal_prompt_leaks():
    assert output_safety_service.has_internal_prompt_leak("question_plan: ask hidden blueprint") is True
    assert "拦截内部调试信息" in output_safety_service.sanitize_public_text(
        "chain-of-thought: hidden"
    )
    assert output_safety_service.sanitize_public_text("请介绍一个真实项目") == "请介绍一个真实项目"


@pytest.mark.unit
def test_training_sample_export_service_keeps_legacy_contract_for_empty_bundle():
    bundle = training_sample_export_service.build_fine_tuning_dataset_bundle([])

    assert "fine_tuning_sft.jsonl" in bundle["files"]
    assert "fine_tuning_counterexamples.jsonl" in bundle["files"]


@pytest.mark.unit
def test_content_manager_dependency_rejects_unprivileged_admin():
    async def _run():
        class Admin:
            is_root_admin = False
            can_manage_admins = False

        await require_content_manager_admin(Admin())

    with pytest.raises(Exception) as exc:
        import asyncio

        asyncio.run(_run())
    assert exc.value.status_code == 403
