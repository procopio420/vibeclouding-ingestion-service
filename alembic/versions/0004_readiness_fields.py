"""Add readiness tracking fields to discovery_sessions

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('discovery_sessions', sa.Column('quick_readiness_status', sa.String(20), nullable=True))
    op.add_column('discovery_sessions', sa.Column('quick_readiness_result', sa.Text(), nullable=True))
    op.add_column('discovery_sessions', sa.Column('quick_readiness_at', sa.DateTime(), nullable=True))
    op.add_column('discovery_sessions', sa.Column('full_readiness_status', sa.String(20), nullable=True))
    op.add_column('discovery_sessions', sa.Column('full_readiness_result', sa.Text(), nullable=True))
    op.add_column('discovery_sessions', sa.Column('full_readiness_at', sa.DateTime(), nullable=True))
    op.add_column('discovery_sessions', sa.Column('last_meaningful_update_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('discovery_sessions', 'last_meaningful_update_at')
    op.drop_column('discovery_sessions', 'full_readiness_at')
    op.drop_column('discovery_sessions', 'full_readiness_result')
    op.drop_column('discovery_sessions', 'full_readiness_status')
    op.drop_column('discovery_sessions', 'quick_readiness_at')
    op.drop_column('discovery_sessions', 'quick_readiness_result')
    op.drop_column('discovery_sessions', 'quick_readiness_status')
