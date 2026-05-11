"""extend_learning_route_plan_fields

Revision ID: f1a2b3c4d5e6
Revises: e3a5b7c9d1f2
Create Date: 2026-05-11 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e3a5b7c9d1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learning_route_stages",
        sa.Column("route_kind", sa.String(length=30), server_default="template", nullable=False),
    )
    op.add_column("learning_route_stages", sa.Column("plan_group", sa.String(length=120), nullable=True))
    op.add_column("learning_route_stages", sa.Column("resource_requirement", sa.Text(), nullable=True))
    op.add_column("learning_route_stages", sa.Column("generation_prompt", sa.Text(), nullable=True))
    op.create_index(op.f("ix_learning_route_stages_route_kind"), "learning_route_stages", ["route_kind"], unique=False)
    op.create_index(op.f("ix_learning_route_stages_plan_group"), "learning_route_stages", ["plan_group"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_route_stages_plan_group"), table_name="learning_route_stages")
    op.drop_index(op.f("ix_learning_route_stages_route_kind"), table_name="learning_route_stages")
    op.drop_column("learning_route_stages", "generation_prompt")
    op.drop_column("learning_route_stages", "resource_requirement")
    op.drop_column("learning_route_stages", "plan_group")
    op.drop_column("learning_route_stages", "route_kind")
