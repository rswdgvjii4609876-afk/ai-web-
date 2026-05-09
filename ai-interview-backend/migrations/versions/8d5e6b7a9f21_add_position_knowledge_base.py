"""add_position_knowledge_base

Revision ID: 8d5e6b7a9f21
Revises: c7f982abaaf0
Create Date: 2026-03-24 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8d5e6b7a9f21'
down_revision: Union[str, None] = 'c7f982abaaf0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector, table_name: str) -> set[str]:
    if table_name not in _table_names(inspector):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    if table_name not in _table_names(inspector):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_key_names(inspector, table_name: str) -> set[str]:
    if table_name not in _table_names(inspector):
        return set()
    return {
        foreign_key["name"]
        for foreign_key in inspector.get_foreign_keys(table_name)
        if foreign_key.get("name")
    }


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'position_knowledge_bases' not in _table_names(inspector):
        op.create_table(
            'position_knowledge_bases',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('target_position', sa.String(length=255), nullable=False),
            sa.Column('knowledge_content', sa.Text(), nullable=False),
            sa.Column('focus_points', sa.Text(), nullable=True),
            sa.Column('interviewer_prompt', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )

    inspector = sa.inspect(bind)
    kb_indexes = _index_names(inspector, 'position_knowledge_bases')
    if op.f('ix_position_knowledge_bases_id') not in kb_indexes:
        op.create_index(op.f('ix_position_knowledge_bases_id'), 'position_knowledge_bases', ['id'], unique=False)
    if op.f('ix_position_knowledge_bases_user_id') not in kb_indexes:
        op.create_index(op.f('ix_position_knowledge_bases_user_id'), 'position_knowledge_bases', ['user_id'], unique=False)
    if op.f('ix_position_knowledge_bases_target_position') not in kb_indexes:
        op.create_index(op.f('ix_position_knowledge_bases_target_position'), 'position_knowledge_bases', ['target_position'], unique=False)

    if 'resumes' not in _table_names(inspector):
        op.create_table(
            'resumes',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('file_url', sa.String(length=500), nullable=True),
            sa.Column('file_name', sa.String(length=255), nullable=True),
            sa.Column('parsed_content', sa.Text(), nullable=True),
            sa.Column('analysis', sa.Text(), nullable=True),
            sa.Column('target_position', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True, server_default='pending'),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_resumes_id'), 'resumes', ['id'], unique=False)
        op.create_index(op.f('ix_resumes_user_id'), 'resumes', ['user_id'], unique=False)

    inspector = sa.inspect(bind)
    if 'interviews' not in _table_names(inspector):
        op.create_table(
            'interviews',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('resume_id', sa.Integer(), nullable=False),
            sa.Column('knowledge_base_id', sa.Integer(), nullable=True),
            sa.Column('target_position', sa.String(length=255), nullable=True),
            sa.Column('difficulty', sa.String(length=20), nullable=True, server_default='medium'),
            sa.Column('total_questions', sa.Integer(), nullable=True, server_default='5'),
            sa.Column('status', sa.String(length=20), nullable=True, server_default='in_progress'),
            sa.Column('current_question_index', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('questions_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('knowledge_base_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('overall_score', sa.DECIMAL(precision=3, scale=1), nullable=True),
            sa.Column('report', sa.Text(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['knowledge_base_id'], ['position_knowledge_bases.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['resume_id'], ['resumes.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_interviews_id'), 'interviews', ['id'], unique=False)
        op.create_index(op.f('ix_interviews_user_id'), 'interviews', ['user_id'], unique=False)
    else:
        interview_columns = _column_names(inspector, 'interviews')
        if 'knowledge_base_id' not in interview_columns:
            op.add_column('interviews', sa.Column('knowledge_base_id', sa.Integer(), nullable=True))
        if 'knowledge_base_snapshot' not in interview_columns:
            op.add_column('interviews', sa.Column('knowledge_base_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

        inspector = sa.inspect(bind)
        foreign_keys = _foreign_key_names(inspector, 'interviews')
        if 'fk_interviews_knowledge_base_id_position_knowledge_bases' not in foreign_keys:
            op.create_foreign_key(
                'fk_interviews_knowledge_base_id_position_knowledge_bases',
                'interviews',
                'position_knowledge_bases',
                ['knowledge_base_id'],
                ['id'],
                ondelete='SET NULL'
            )

    inspector = sa.inspect(bind)
    if 'interview_messages' not in _table_names(inspector):
        op.create_table(
            'interview_messages',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('interview_id', sa.Integer(), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('question_index', sa.Integer(), nullable=True),
            sa.Column('score', sa.DECIMAL(precision=3, scale=1), nullable=True),
            sa.Column('feedback', sa.Text(), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.ForeignKeyConstraint(['interview_id'], ['interviews.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_interview_messages_id'), 'interview_messages', ['id'], unique=False)
        op.create_index(op.f('ix_interview_messages_interview_id'), 'interview_messages', ['interview_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_interviews_knowledge_base_id_position_knowledge_bases', 'interviews', type_='foreignkey')
    op.drop_column('interviews', 'knowledge_base_snapshot')
    op.drop_column('interviews', 'knowledge_base_id')

    op.drop_index(op.f('ix_position_knowledge_bases_target_position'), table_name='position_knowledge_bases')
    op.drop_index(op.f('ix_position_knowledge_bases_user_id'), table_name='position_knowledge_bases')
    op.drop_index(op.f('ix_position_knowledge_bases_id'), table_name='position_knowledge_bases')
    op.drop_table('position_knowledge_bases')
