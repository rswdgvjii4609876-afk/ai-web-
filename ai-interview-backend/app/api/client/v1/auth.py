import os
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.client.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.client.auth import (
    AccessToken,
    AuthToken,
    Login,
    LogoutRequest,
    PasswordResetToken,
    RefreshTokenRequest,
    RegisterResponse,
    ResetPassword,
    SendCodeResponse,
    SendPasswordResetCode,
    SendVerificationCode,
    UserRegister,
    VerifyEmail,
    VerifyPasswordResetCode,
)
from app.schemas.client.user import UserProfile
from app.schemas.response import ApiResponse
from app.services.client.auth import client_auth_service
from app.services.common.deepseek_config_service import deepseek_config_service

router = APIRouter()


@router.post("/register", response_model=AuthToken)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    result = await client_auth_service.register_user(db, user_data.model_dump())
    return ApiResponse.success(data=result)


@router.post("/send-verification-code", response_model=SendCodeResponse)
async def send_verification_code(
    request: SendVerificationCode,
    db: AsyncSession = Depends(get_db),
):
    result = await client_auth_service.send_verification_code(
        db, request.email, request.code_type
    )
    return ApiResponse.success(data=result)


@router.post("/verify-email", response_model=AuthToken)
async def verify_email(
    request: VerifyEmail,
    db: AsyncSession = Depends(get_db),
):
    result = await client_auth_service.verify_email_and_login(
        db, request.email, request.code
    )
    return ApiResponse.success(data=result)


@router.post("/login", response_model=AuthToken)
async def login(
    login_data: Login,
    db: AsyncSession = Depends(get_db),
):
    result = await client_auth_service.login(
        db, login_data.email, login_data.password, login_data.remember_me
    )
    return ApiResponse.success(data=result)


@router.post("/refresh", response_model=AccessToken)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await client_auth_service.refresh_token(db, request.refresh_token)
    return ApiResponse.success(data=result)


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    await client_auth_service.logout(db, request.refresh_token)
    return ApiResponse.success_without_data()


@router.post("/password-reset/send-code")
async def send_password_reset_code(
    request: SendPasswordResetCode,
    db: AsyncSession = Depends(get_db),
):
    result = await client_auth_service.send_verification_code(
        db, request.email, "password-reset"
    )
    return ApiResponse.success(data=result)


@router.post("/password-reset/verify-code", response_model=PasswordResetToken)
async def verify_password_reset_code(
    request: VerifyPasswordResetCode,
    db: AsyncSession = Depends(get_db),
):
    reset_token = await client_auth_service.verify_password_reset_code(
        db, request.email, request.code
    )
    return ApiResponse.success(
        data={
            "reset_token": reset_token,
            "expires_in": 900,
        }
    )


@router.post("/password-reset/reset")
async def reset_password(
    request: ResetPassword,
    db: AsyncSession = Depends(get_db),
):
    await client_auth_service.reset_password(
        db, request.reset_token, request.new_password
    )
    return ApiResponse.success_without_data(message="密码重置成功，请重新登录")


def _serialize_user_profile(current_user: User) -> dict:
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "avatar": current_user.avatar,
        "phone": current_user.phone,
        "phone_country_code": current_user.phone_country_code,
        "university": current_user.university,
        "career_goal": current_user.career_goal,
        "contract_types": current_user.contract_types,
        "location": current_user.location,
        "gender": current_user.gender,
        "is_verified": current_user.is_verified,
        "email_verified_at": current_user.email_verified_at.isoformat()
        if current_user.email_verified_at
        else None,
        "last_active_at": current_user.last_active_at.isoformat()
        if current_user.last_active_at
        else None,
        **deepseek_config_service.summarize_for_profile(current_user),
    }


@router.get("/me", response_model=UserProfile)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    return ApiResponse.success(data=_serialize_user_profile(current_user))


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    university: Optional[str] = None
    career_goal: Optional[str] = None
    location: Optional[str] = None
    gender: Optional[str] = None
    ai_provider: Optional[str] = None
    deepseek_use_personal_api: Optional[bool] = None
    deepseek_api_key: Optional[str] = None
    clear_deepseek_api_key: bool = False
    deepseek_base_url: Optional[str] = None
    deepseek_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    clear_openai_api_key: bool = False
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None


class AIConnectionTestRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None


@router.put("/me")
async def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("deepseek_use_personal_api", None)
    ai_provider = update_data.pop("ai_provider", None)
    clear_deepseek_api_key = update_data.pop("clear_deepseek_api_key", False)
    deepseek_api_key = update_data.pop("deepseek_api_key", None)
    clear_openai_api_key = update_data.pop("clear_openai_api_key", False)
    openai_api_key = update_data.pop("openai_api_key", None)
    profile_message = "资料更新成功"

    if clear_deepseek_api_key:
        current_user.deepseek_api_key_encrypted = None
        profile_message = "资料更新成功，已删除你的 DeepSeek API Key"

    if deepseek_api_key is not None:
        cleaned_key = deepseek_api_key.strip()
        if cleaned_key:
            current_user.deepseek_api_key_encrypted = deepseek_config_service.encrypt_api_key(
                cleaned_key
            )
            profile_message = "资料更新成功，你的 DeepSeek API Key 已保存"

    if clear_openai_api_key:
        current_user.openai_api_key_encrypted = None
        profile_message = "资料更新成功，已删除你的 ChatGPT / OpenAI API Key"

    if openai_api_key is not None:
        cleaned_key = openai_api_key.strip()
        if cleaned_key:
            current_user.openai_api_key_encrypted = deepseek_config_service.encrypt_api_key(
                cleaned_key
            )
            profile_message = "资料更新成功，你的 ChatGPT / OpenAI API Key 已保存"

    if ai_provider is not None:
        current_user.ai_provider = deepseek_config_service.normalize_provider(ai_provider)

    if "deepseek_base_url" in update_data:
        update_data["deepseek_base_url"] = (
            update_data["deepseek_base_url"].strip() or None
            if update_data["deepseek_base_url"] is not None
            else None
        )
    if "deepseek_model" in update_data:
        update_data["deepseek_model"] = (
            update_data["deepseek_model"].strip() or None
            if update_data["deepseek_model"] is not None
            else None
        )
    if "openai_base_url" in update_data:
        update_data["openai_base_url"] = (
            update_data["openai_base_url"].strip() or None
            if update_data["openai_base_url"] is not None
            else None
        )
    if "openai_model" in update_data:
        update_data["openai_model"] = (
            update_data["openai_model"].strip() or None
            if update_data["openai_model"] is not None
            else None
        )

    for key, value in update_data.items():
        setattr(current_user, key, value)

    selected_provider = deepseek_config_service.normalize_provider(current_user.ai_provider)
    selected_provider_label = deepseek_config_service.provider_label(selected_provider)
    if selected_provider == "openai" and not current_user.openai_api_key_encrypted:
        return ApiResponse.error(
            message=f"切换到 {selected_provider_label} 前，请先保存对应的 API Key"
        )
    if selected_provider == "deepseek" and not current_user.deepseek_api_key_encrypted:
        return ApiResponse.error(message="切换到 DeepSeek 前，请先保存对应的 API Key")

    current_user.deepseek_use_personal_api = (
        selected_provider == "deepseek" and bool(current_user.deepseek_api_key_encrypted)
    )

    await db.commit()
    await db.refresh(current_user)
    return ApiResponse.success(
        data={
            "message": profile_message,
            **deepseek_config_service.summarize_for_profile(current_user),
        }
    )


@router.post("/me/ai-connection-test")
async def test_ai_connection(
    data: AIConnectionTestRequest,
    current_user: User = Depends(get_current_user),
):
    from app.services.client.ai_service import AIService

    runtime_config = deepseek_config_service.build_runtime_config(
        current_user,
        require_personal_key=True,
        provider=data.provider,
    )
    if data.model is not None and data.model.strip():
        runtime_config["model"] = data.model.strip()
    result = await AIService.test_runtime_connection(runtime_config)
    return ApiResponse.success(data=result)


AVATAR_DIR = "uploads/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        return ApiResponse.error(message="仅支持图片文件")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        return ApiResponse.error(message="文件大小不能超过 5MB")

    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{current_user.id}.{ext}"
    filepath = os.path.join(AVATAR_DIR, filename)

    with open(filepath, "wb") as file_obj:
        file_obj.write(content)

    current_user.avatar = f"/uploads/avatars/{filename}"
    await db.commit()
    return ApiResponse.success(data={"avatar": current_user.avatar})


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


@router.post("/me/change-password")
async def change_password(
    data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.verify_password(data.old_password):
        return ApiResponse.error(message="当前密码不正确")

    if len(data.new_password) < 6:
        return ApiResponse.error(message="新密码至少 6 位")

    current_user.hashed_password = User.get_password_hash(data.new_password)
    await db.commit()
    return ApiResponse.success(data={"message": "密码修改成功"})
