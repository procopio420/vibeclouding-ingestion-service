"""Add discovery session, chat messages, checklist, and questions tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'discovery_sessions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('state', sa.String(50), nullable=False, server_default='collecting_initial_context'),
        sa.Column('readiness_status', sa.String(50), nullable=False, server_default='not_ready'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_transition_at', sa.DateTime(), nullable=True),
        sa.Column('last_user_message_at', sa.DateTime(), nullable=True),
        sa.Column('last_system_message_at', sa.DateTime(), nullable=True),
        sa.Column('active_ingestion_job_ids', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_discovery_sessions_project_id', 'discovery_sessions', ['project_id'])
    op.create_index('ix_discovery_sessions_state', 'discovery_sessions', ['state'])

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['session_id'], ['discovery_sessions.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_messages_project_id', 'chat_messages', ['project_id'])
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])

    op.create_table(
        'checklist_items',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('key', sa.String(50), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='missing'),
        sa.Column('priority', sa.String(20), nullable=True),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_checklist_items_project_id', 'checklist_items', ['project_id'])
    op.create_index('ix_checklist_items_key', 'checklist_items', ['key'])

    op.create_table(
        'clarification_questions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('related_checklist_key', sa.String(50), nullable=True),
        sa.Column('answer_source', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_clarification_questions_project_id', 'clarification_questions', ['project_id'])
    op.create_index('ix_clarification_questions_status', 'clarification_questions', ['status'])


def downgrade():
    op.drop_index('ix_clarification_questions_status', 'clarification_questions')
    op.drop_index('ix_clarification_questions_project_id', 'clarification_questions')
    op.drop_table('clarification_questions')
    op.drop_index('ix_checklist_items_key', 'checklist_items')
    op.drop_index('ix_checklist_items_project_id', 'checklist_items')
    op.drop_table('checklist_items')
    op.drop_index('ix_chat_messages_created_at', 'chat_messages')
    op.drop_index('ix_chat_messages_session_id', 'chat_messages')
    op.drop_index('ix_chat_messages_project_id', 'chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('ix_discovery_sessions_state', 'discovery_sessions')
    op.drop_index('ix_discovery_sessions_project_id', 'discovery_sessions')
    op.drop_table('discovery_sessions')
