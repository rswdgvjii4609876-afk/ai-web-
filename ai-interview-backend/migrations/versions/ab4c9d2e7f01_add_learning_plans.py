"""add_learning_plans

Revision ID: ab4c9d2e7f01
Revises: e8b6c4a2d913
Create Date: 2026-05-21 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ab4c9d2e7f01"
down_revision: Union[str, None] = "e8b6c4a2d913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_resume_id", sa.Integer(), nullable=True),
        sa.Column("source_interview_id", sa.Integer(), nullable=True),
        sa.Column("previous_plan_id", sa.Integer(), nullable=True),
        sa.Column("target_position", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("plan_days", sa.Integer(), nullable=True),
        sa.Column("daily_minutes", sa.Integer(), nullable=True),
        sa.Column("selected_abilities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("plan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generation_backend", sa.String(length=80), nullable=True),
        sa.Column("web_search_status", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["previous_plan_id"], ["learning_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_interview_id"], ["interviews.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_learning_plans_id"), "learning_plans", ["id"], unique=False)
    op.create_index(op.f("ix_learning_plans_user_id"), "learning_plans", ["user_id"], unique=False)
    op.create_index(op.f("ix_learning_plans_source_resume_id"), "learning_plans", ["source_resume_id"], unique=False)
    op.create_index(op.f("ix_learning_plans_source_interview_id"), "learning_plans", ["source_interview_id"], unique=False)
    op.create_index(op.f("ix_learning_plans_previous_plan_id"), "learning_plans", ["previous_plan_id"], unique=False)
    op.create_index(op.f("ix_learning_plans_status"), "learning_plans", ["status"], unique=False)
    op.add_column("learning_tasks", sa.Column("learning_plan_id", sa.Integer(), nullable=True))
    op.add_column("learning_tasks", sa.Column("step_order", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_learning_tasks_learning_plan_id"), "learning_tasks", ["learning_plan_id"], unique=False)
    op.create_foreign_key(
        "fk_learning_tasks_learning_plan_id_learning_plans",
        "learning_tasks",
        "learning_plans",
        ["learning_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_learning_tasks_learning_plan_id_learning_plans", "learning_tasks", type_="foreignkey")
    op.drop_index(op.f("ix_learning_tasks_learning_plan_id"), table_name="learning_tasks")
    op.drop_column("learning_tasks", "step_order")
    op.drop_column("learning_tasks", "learning_plan_id")
    op.drop_index(op.f("ix_learning_plans_status"), table_name="learning_plans")
    op.drop_index(op.f("ix_learning_plans_previous_plan_id"), table_name="learning_plans")
    op.drop_index(op.f("ix_learning_plans_source_interview_id"), table_name="learning_plans")
    op.drop_index(op.f("ix_learning_plans_source_resume_id"), table_name="learning_plans")
    op.drop_index(op.f("ix_learning_plans_user_id"), table_name="learning_plans")
    op.drop_index(op.f("ix_learning_plans_id"), table_name="learning_plans")
    op.drop_table("learning_plans")
