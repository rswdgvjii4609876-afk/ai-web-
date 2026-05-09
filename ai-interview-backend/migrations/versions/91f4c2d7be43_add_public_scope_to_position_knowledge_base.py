"""add_public_scope_to_position_knowledge_base

Revision ID: 91f4c2d7be43
Revises: 8d5e6b7a9f21
Create Date: 2026-03-24 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91f4c2d7be43'
down_revision: Union[str, None] = '8d5e6b7a9f21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'position_knowledge_bases',
        sa.Column('admin_id', sa.Integer(), nullable=True)
    )
    op.add_column(
        'position_knowledge_bases',
        sa.Column('scope', sa.String(length=20), nullable=False, server_default=sa.text("'private'"))
    )
    op.create_index(op.f('ix_position_knowledge_bases_admin_id'), 'position_knowledge_bases', ['admin_id'], unique=False)
    op.create_index(op.f('ix_position_knowledge_bases_scope'), 'position_knowledge_bases', ['scope'], unique=False)
    op.create_foreign_key(
        'fk_position_knowledge_bases_admin_id_admins',
        'position_knowledge_bases',
        'admins',
        ['admin_id'],
        ['id']
    )
    op.alter_column(
        'position_knowledge_bases',
        'user_id',
        existing_type=sa.Integer(),
        nullable=True
    )
    op.execute("UPDATE position_knowledge_bases SET scope = 'private' WHERE scope IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM position_knowledge_bases WHERE scope = 'public'")
    op.alter_column(
        'position_knowledge_bases',
        'user_id',
        existing_type=sa.Integer(),
        nullable=False
    )
    op.drop_constraint('fk_position_knowledge_bases_admin_id_admins', 'position_knowledge_bases', type_='foreignkey')
    op.drop_index(op.f('ix_position_knowledge_bases_scope'), table_name='position_knowledge_bases')
    op.drop_index(op.f('ix_position_knowledge_bases_admin_id'), table_name='position_knowledge_bases')
    op.drop_column('position_knowledge_bases', 'scope')
    op.drop_column('position_knowledge_bases', 'admin_id')
