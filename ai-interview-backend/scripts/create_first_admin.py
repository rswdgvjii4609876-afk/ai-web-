"""Create the first backoffice admin account for production bootstrapping."""

import asyncio
import os
import re
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Add project root to Python path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.base import get_engine
from app.models.admin import Admin


PASSWORD_REQUIREMENTS = (
    "INIT_ADMIN_PASSWORD must be at least 12 characters and include letters, "
    "numbers, and special characters."
)


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required.")
    return value


def _validate_email(email: str) -> None:
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise SystemExit("INIT_ADMIN_EMAIL is invalid.")


def _validate_password(password: str) -> None:
    if len(password) < 12:
        raise SystemExit(PASSWORD_REQUIREMENTS)
    if not re.search(r"[A-Za-z]", password):
        raise SystemExit(PASSWORD_REQUIREMENTS)
    if not re.search(r"\d", password):
        raise SystemExit(PASSWORD_REQUIREMENTS)
    if not re.search(r"[^A-Za-z0-9]", password):
        raise SystemExit(PASSWORD_REQUIREMENTS)


def _load_admin_config() -> tuple[str, str, str, str]:
    email = _get_required_env("INIT_ADMIN_EMAIL")
    password = _get_required_env("INIT_ADMIN_PASSWORD")
    first_name = os.getenv("INIT_ADMIN_FIRST_NAME", "AI-Interview").strip() or "AI-Interview"
    last_name = os.getenv("INIT_ADMIN_LAST_NAME", "Admin").strip() or "Admin"

    _validate_email(email)
    _validate_password(password)
    return email, password, first_name, last_name


async def create_first_admin() -> None:
    """Create the first superadmin account if it does not exist."""
    email, password, first_name, last_name = _load_admin_config()

    engine = get_engine()
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Admin).where(Admin.email == email))
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print(f"Admin already exists: {email} (id={existing_admin.id})")
            return

        admin = Admin(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=Admin.get_password_hash(password),
            role="superadmin",
            is_active=True,
        )

        session.add(admin)
        await session.commit()
        await session.refresh(admin)

        print("Initial superadmin created successfully.")
        print(f"Email: {email}")
        print(f"Name: {first_name} {last_name}")
        print("Role: superadmin")
        print(f"ID: {admin.id}")
        print("Next step: sign in to the admin panel and change the password immediately.")


if __name__ == "__main__":
    asyncio.run(create_first_admin())
