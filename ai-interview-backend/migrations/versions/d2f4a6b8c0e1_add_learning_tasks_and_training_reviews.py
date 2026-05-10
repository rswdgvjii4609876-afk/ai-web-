"""add_learning_tasks_and_training_reviews

Revision ID: d2f4a6b8c0e1
Revises: b9e3a4f1c2d0
Create Date: 2026-05-10 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d2f4a6b8c0e1"
down_revision: Union[str, None] = "b9e3a4f1c2d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_key", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("ability_name", sa.String(length=255), nullable=True),
        sa.Column("target_position", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("resume_id", sa.Integer(), nullable=True),
        sa.Column("interview_id", sa.Integer(), nullable=True),
        sa.Column("priority_score", sa.String(length=50), nullable=True),
        sa.Column("route_source", sa.String(length=100), nullable=True),
        sa.Column("route_stage", sa.String(length=100), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.String(length=20), nullable=True),
        sa.Column("learning_material", sa.Text(), nullable=True),
        sa.Column("practice_task", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("task_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_basis", sa.Text(), nullable=True),
        sa.Column("done", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("weak_change", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "task_key", name="uq_learning_tasks_user_task_key"),
    )
    op.create_index(op.f("ix_learning_tasks_id"), "learning_tasks", ["id"], unique=False)
    op.create_index(op.f("ix_learning_tasks_user_id"), "learning_tasks", ["user_id"], unique=False)

    op.create_table(
        "training_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("interview_id", sa.Integer(), nullable=False),
        sa.Column("self_rating", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("next_goal", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "interview_id", name="uq_training_reviews_user_interview"),
    )
    op.create_index(op.f("ix_training_reviews_id"), "training_reviews", ["id"], unique=False)
    op.create_index(op.f("ix_training_reviews_interview_id"), "training_reviews", ["interview_id"], unique=False)
    op.create_index(op.f("ix_training_reviews_user_id"), "training_reviews", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_training_reviews_user_id"), table_name="training_reviews")
    op.drop_index(op.f("ix_training_reviews_interview_id"), table_name="training_reviews")
    op.drop_index(op.f("ix_training_reviews_id"), table_name="training_reviews")
    op.drop_table("training_reviews")

    op.drop_index(op.f("ix_learning_tasks_user_id"), table_name="learning_tasks")
    op.drop_index(op.f("ix_learning_tasks_id"), table_name="learning_tasks")
    op.drop_table("learning_tasks")
