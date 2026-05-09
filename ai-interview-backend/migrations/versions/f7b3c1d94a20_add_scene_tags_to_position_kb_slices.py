"""add_scene_tags_to_position_kb_slices

Revision ID: f7b3c1d94a20
Revises: e4a1b9c52f30
Create Date: 2026-03-25 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f7b3c1d94a20"
down_revision: Union[str, None] = "e4a1b9c52f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "position_knowledge_base_slices",
        sa.Column("scene_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("position_knowledge_base_slices", "scene_tags")
