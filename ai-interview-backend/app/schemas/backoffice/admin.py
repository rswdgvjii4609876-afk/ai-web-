from ..base import BaseSchema, BaseResponseSchema, add_padded_id
from pydantic import EmailStr, Field
from typing import Optional


class AdminBase(BaseSchema):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    can_manage_admins: Optional[bool] = False
    can_review_cases: Optional[bool] = False
    can_export_datasets: Optional[bool] = False
    can_delete_records: Optional[bool] = False


class AdminCreate(AdminBase):
    password: str = Field(..., min_length=8)


class AdminUpdate(BaseSchema):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    can_manage_admins: Optional[bool] = None
    can_review_cases: Optional[bool] = None
    can_export_datasets: Optional[bool] = None
    can_delete_records: Optional[bool] = None

@add_padded_id()
class AdminResponse(BaseResponseSchema, AdminBase):
    is_active: bool
    can_manage_admins: bool = False
    can_review_cases: bool = False
    can_export_datasets: bool = False
    can_delete_records: bool = False
    role: Optional[str] = None
    is_root_admin: bool = False
    padded_id: Optional[str] = None

    @classmethod
    def model_validate(cls, admin):
        return super().model_validate(admin)


class AdminChangePassword(BaseSchema):
    current_password: str
    new_password: str = Field(..., min_length=8)

class ResetPassword(BaseSchema):
    password: str = Field(..., min_length=8)


class AdminFilter(BaseSchema):
    email: Optional[str] = None
    is_active: Optional[bool] = None
