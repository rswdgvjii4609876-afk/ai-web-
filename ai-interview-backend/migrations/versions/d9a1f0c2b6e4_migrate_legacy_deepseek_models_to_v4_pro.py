"""Migrate legacy DeepSeek model aliases to V4 Pro.

Revision ID: d9a1f0c2b6e4
Revises: c5f2a7b9d153
Create Date: 2026-05-20 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d9a1f0c2b6e4"
down_revision: Union[str, None] = "c5f2a7b9d153"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET deepseek_model = 'deepseek-v4-pro'
        WHERE deepseek_model IN ('deepseek-chat', 'deepseek-reasoner')
        """
    )


def downgrade() -> None:
    # This migration intentionally does not restore retired legacy aliases.
    pass
