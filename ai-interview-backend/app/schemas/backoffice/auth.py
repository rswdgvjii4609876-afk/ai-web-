from ..base import BaseSchema, BaseResponseSchema
from pydantic import EmailStr
from datetime import datetime
from typing import Optional


class Login(BaseSchema):
    email: EmailStr
    password: str


class Token(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshToken(BaseSchema):
    refresh_token: str


class Logout(BaseSchema):
    refresh_token: str


class AdminInfo(BaseResponseSchema):
    id: int
    role: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    can_manage_admins: bool = False
    can_review_cases: bool = False
    can_export_datasets: bool = False
    can_delete_records: bool = False
    is_root_admin: bool = False
    created_at: datetime
    updated_at: datetime
