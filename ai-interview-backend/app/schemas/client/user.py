from typing import List, Optional

from ..base import BaseSchema


class UserProfile(BaseSchema):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    avatar: Optional[str] = None
    phone: Optional[str]
    phone_country_code: Optional[str]
    university: Optional[str]
    career_goal: Optional[str]
    contract_types: Optional[List[str]]
    location: Optional[str]
    gender: Optional[str] = None
    is_verified: bool
    email_verified_at: Optional[str] = None
    last_active_at: Optional[str] = None
    ai_provider: str = "deepseek"
    deepseek_use_personal_api: bool = False
    deepseek_has_personal_api_key: bool = False
    deepseek_base_url: Optional[str] = None
    deepseek_model: Optional[str] = None
    openai_has_personal_api_key: bool = False
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None


class UserUpdate(BaseSchema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar: Optional[str] = None
    phone: Optional[str] = None
    phone_country_code: Optional[str] = None
    university: Optional[str] = None
    career_goal: Optional[str] = None
    contract_types: Optional[List[str]] = None
    location: Optional[str] = None
    gender: Optional[str] = None
    ai_provider: Optional[str] = None
    deepseek_use_personal_api: Optional[bool] = None
    deepseek_api_key: Optional[str] = None
    clear_deepseek_api_key: Optional[bool] = False
    deepseek_base_url: Optional[str] = None
    deepseek_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    clear_openai_api_key: Optional[bool] = False
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None


class ChangePassword(BaseSchema):
    current_password: str
    new_password: str
    confirm_password: str
