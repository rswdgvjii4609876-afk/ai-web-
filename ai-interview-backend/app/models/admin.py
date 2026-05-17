from sqlalchemy import Boolean, Column, Integer, String, Enum
from .base import BaseModel
from passlib.context import CryptContext
from sqlalchemy.orm import relationship

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ROOT_ADMIN_EMAIL = "autsky6666@gmail.com"


class UserRole(str, Enum):
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class Admin(BaseModel):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role = Column(String(20), default=UserRole.ADMIN, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    can_manage_admins = Column(Boolean, default=False, nullable=False)
    can_review_cases = Column(Boolean, default=False, nullable=False)
    can_export_datasets = Column(Boolean, default=False, nullable=False)
    can_delete_records = Column(Boolean, default=False, nullable=False)

    @property
    def is_root_admin(self) -> bool:
        return (self.email or "").strip().lower() == ROOT_ADMIN_EMAIL

    @staticmethod
    def get_password_hash(password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str) -> bool:
        return pwd_context.verify(plain_password, self.password)
