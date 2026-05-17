"""add_admin_data_permissions

Revision ID: c5f2a7b9d153
Revises: b7d9e1f3a5c8
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5f2a7b9d153"
down_revision: Union[str, None] = "b7d9e1f3a5c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROOT_ADMIN_EMAIL = "autsky6666@gmail.com"


def upgrade() -> None:
    for column_name in (
        "can_review_cases",
        "can_export_datasets",
        "can_delete_records",
    ):
        op.add_column(
            "admins",
            sa.Column(column_name, sa.Boolean(), server_default=sa.false(), nullable=False),
        )

    op.execute(
        f"update admins set "
        f"can_review_cases = true, "
        f"can_export_datasets = true, "
        f"can_delete_records = true "
        f"where lower(email) = lower('{ROOT_ADMIN_EMAIL}')"
    )


def downgrade() -> None:
    op.drop_column("admins", "can_delete_records")
    op.drop_column("admins", "can_export_datasets")
    op.drop_column("admins", "can_review_cases")
