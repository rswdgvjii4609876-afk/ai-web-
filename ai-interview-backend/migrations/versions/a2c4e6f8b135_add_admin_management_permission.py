"""add_admin_management_permission

Revision ID: a2c4e6f8b135
Revises: f1a2b3c4d5e6
Create Date: 2026-05-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2c4e6f8b135"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROOT_ADMIN_EMAIL = "autsky6666@gmail.com"


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column("can_manage_admins", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute(
        f"update admins set can_manage_admins = true, role = 'superadmin' "
        f"where lower(email) = lower('{ROOT_ADMIN_EMAIL}')"
    )


def downgrade() -> None:
    op.drop_column("admins", "can_manage_admins")
