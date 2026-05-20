"""Add user-side soft delete fields to interviews.

Revision ID: e8b6c4a2d913
Revises: d9a1f0c2b6e4
Create Date: 2026-05-20 20:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8b6c4a2d913"
down_revision: Union[str, None] = "d9a1f0c2b6e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interviews", sa.Column("user_deleted_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("interviews", sa.Column("user_deleted_reason", sa.String(length=255), nullable=True))
    op.create_index("ix_interviews_user_deleted_at", "interviews", ["user_deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interviews_user_deleted_at", table_name="interviews")
    op.drop_column("interviews", "user_deleted_reason")
    op.drop_column("interviews", "user_deleted_at")
