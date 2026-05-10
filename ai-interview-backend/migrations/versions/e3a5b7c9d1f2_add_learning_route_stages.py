"""add_learning_route_stages

Revision ID: e3a5b7c9d1f2
Revises: d2f4a6b8c0e1
Create Date: 2026-05-10 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e3a5b7c9d1f2"
down_revision: Union[str, None] = "d2f4a6b8c0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_route_stages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=True),
        sa.Column("job_name", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("route_source", sa.String(length=120), nullable=False),
        sa.Column("route_stage", sa.String(length=120), nullable=False),
        sa.Column("stage_title", sa.String(length=255), nullable=False),
        sa.Column("material_type", sa.String(length=100), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("learning_material", sa.Text(), nullable=True),
        sa.Column("practice_task", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_route_stages_id"), "learning_route_stages", ["id"], unique=False)
    op.create_index(op.f("ix_learning_route_stages_job_id"), "learning_route_stages", ["job_id"], unique=False)
    op.create_index(op.f("ix_learning_route_stages_category"), "learning_route_stages", ["category"], unique=False)
    op.create_index(op.f("ix_learning_route_stages_route_source"), "learning_route_stages", ["route_source"], unique=False)
    op.create_index(op.f("ix_learning_route_stages_route_stage"), "learning_route_stages", ["route_stage"], unique=False)
    op.create_index(op.f("ix_learning_route_stages_task_type"), "learning_route_stages", ["task_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_route_stages_task_type"), table_name="learning_route_stages")
    op.drop_index(op.f("ix_learning_route_stages_route_stage"), table_name="learning_route_stages")
    op.drop_index(op.f("ix_learning_route_stages_route_source"), table_name="learning_route_stages")
    op.drop_index(op.f("ix_learning_route_stages_category"), table_name="learning_route_stages")
    op.drop_index(op.f("ix_learning_route_stages_job_id"), table_name="learning_route_stages")
    op.drop_index(op.f("ix_learning_route_stages_id"), table_name="learning_route_stages")
    op.drop_table("learning_route_stages")
