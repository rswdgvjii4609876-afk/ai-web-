"""add_position_knowledge_base_slices

Revision ID: c3f8a6b1d201
Revises: 91f4c2d7be43
Create Date: 2026-03-25 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c3f8a6b1d201"
down_revision: Union[str, None] = "91f4c2d7be43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "position_knowledge_base_slices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("slice_type", sa.String(length=50), nullable=False, server_default="knowledge"),
        sa.Column("source_section", sa.String(length=50), nullable=True),
        sa.Column("source_scope", sa.String(length=20), nullable=False, server_default="private"),
        sa.Column("difficulty", sa.String(length=20), nullable=False, server_default="general"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("role_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("topic_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("skill_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["position_knowledge_bases.id"],
            ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_position_knowledge_base_slices_id"),
        "position_knowledge_base_slices",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_position_knowledge_base_slices_knowledge_base_id"),
        "position_knowledge_base_slices",
        ["knowledge_base_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_position_knowledge_base_slices_slice_type"),
        "position_knowledge_base_slices",
        ["slice_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_position_knowledge_base_slices_source_scope"),
        "position_knowledge_base_slices",
        ["source_scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_position_knowledge_base_slices_difficulty"),
        "position_knowledge_base_slices",
        ["difficulty"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_position_knowledge_base_slices_difficulty"), table_name="position_knowledge_base_slices")
    op.drop_index(op.f("ix_position_knowledge_base_slices_source_scope"), table_name="position_knowledge_base_slices")
    op.drop_index(op.f("ix_position_knowledge_base_slices_slice_type"), table_name="position_knowledge_base_slices")
    op.drop_index(op.f("ix_position_knowledge_base_slices_knowledge_base_id"), table_name="position_knowledge_base_slices")
    op.drop_index(op.f("ix_position_knowledge_base_slices_id"), table_name="position_knowledge_base_slices")
    op.drop_table("position_knowledge_base_slices")
