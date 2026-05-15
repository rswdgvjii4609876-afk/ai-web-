"""add_privacy_consent_fields

Revision ID: b7d9e1f3a5c8
Revises: a2c4e6f8b135
Create Date: 2026-05-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7d9e1f3a5c8"
down_revision: Union[str, None] = "a2c4e6f8b135"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("privacy_policy_version", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("privacy_agreed_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "data_contribution_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("data_contribution_consent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("data_contribution_withdrawn_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("data_contribution_consent_version", sa.String(length=50), nullable=True),
    )

    op.add_column(
        "resumes",
        sa.Column(
            "data_contribution_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column("resumes", sa.Column("privacy_consent_snapshot", sa.JSON(), nullable=True))

    op.add_column(
        "interviews",
        sa.Column(
            "data_contribution_consent",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "interviews",
        sa.Column("privacy_consent_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interviews", "privacy_consent_snapshot")
    op.drop_column("interviews", "data_contribution_consent")
    op.drop_column("resumes", "privacy_consent_snapshot")
    op.drop_column("resumes", "data_contribution_consent")
    op.drop_column("users", "data_contribution_consent_version")
    op.drop_column("users", "data_contribution_withdrawn_at")
    op.drop_column("users", "data_contribution_consent_at")
    op.drop_column("users", "data_contribution_consent")
    op.drop_column("users", "privacy_agreed_at")
    op.drop_column("users", "privacy_policy_version")
