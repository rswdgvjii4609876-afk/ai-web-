"""add_openai_provider_fields_to_users

Revision ID: b9e3a4f1c2d0
Revises: aa7b1c9e42f0
Create Date: 2026-03-26 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9e3a4f1c2d0"
down_revision: Union[str, None] = "aa7b1c9e42f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "ai_provider",
            sa.String(length=20),
            nullable=False,
            server_default="deepseek",
        ),
    )
    op.add_column(
        "users",
        sa.Column("openai_api_key_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("openai_base_url", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("openai_model", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "openai_model")
    op.drop_column("users", "openai_base_url")
    op.drop_column("users", "openai_api_key_encrypted")
    op.drop_column("users", "ai_provider")
