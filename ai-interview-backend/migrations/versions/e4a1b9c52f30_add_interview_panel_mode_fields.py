"""add_interview_panel_mode_fields

Revision ID: e4a1b9c52f30
Revises: c3f8a6b1d201
Create Date: 2026-03-25 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e4a1b9c52f30"
down_revision: Union[str, None] = "c3f8a6b1d201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "interviews" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("interviews")}
    if "interview_mode" not in columns:
        op.add_column(
            "interviews",
            sa.Column("interview_mode", sa.String(length=20), nullable=False, server_default="single"),
        )
    if "panel_snapshot" not in columns:
        op.add_column(
            "interviews",
            sa.Column("panel_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    index_names = {index["name"] for index in inspector.get_indexes("interviews")}
    if op.f("ix_interviews_interview_mode") not in index_names:
        op.create_index(op.f("ix_interviews_interview_mode"), "interviews", ["interview_mode"], unique=False)

    op.execute("UPDATE interviews SET interview_mode = 'single' WHERE interview_mode IS NULL")


def downgrade() -> None:
    op.drop_index(op.f("ix_interviews_interview_mode"), table_name="interviews")
    op.drop_column("interviews", "panel_snapshot")
    op.drop_column("interviews", "interview_mode")
