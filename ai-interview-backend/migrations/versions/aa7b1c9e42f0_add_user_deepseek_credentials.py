"""add_user_deepseek_credentials

Revision ID: aa7b1c9e42f0
Revises: f7b3c1d94a20
Create Date: 2026-03-26 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aa7b1c9e42f0"
down_revision: Union[str, None] = "f7b3c1d94a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "deepseek_use_personal_api",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("deepseek_api_key_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("deepseek_base_url", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("deepseek_model", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "deepseek_model")
    op.drop_column("users", "deepseek_base_url")
    op.drop_column("users", "deepseek_api_key_encrypted")
    op.drop_column("users", "deepseek_use_personal_api")
