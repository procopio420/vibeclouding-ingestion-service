"""Add architecture_results table and project status

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('projects', sa.Column('status', sa.String(50), server_default='created'))
    
    op.create_table(
        'architecture_results',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('schema_version', sa.String(20), nullable=True, server_default='1.0'),
        sa.Column('analise_entrada', sa.Text(), nullable=True),
        sa.Column('vibe_economica', sa.Text(), nullable=True),
        sa.Column('vibe_performance', sa.Text(), nullable=True),
        sa.Column('raw_payload', sa.Text(), nullable=True),
        sa.Column('raw_payload_storage_key', sa.String(512), nullable=True),
        sa.Column('is_latest', sa.String(10), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_architecture_results_project_id', 'architecture_results', ['project_id'])


def downgrade():
    op.drop_index('ix_architecture_results_project_id', 'architecture_results')
    op.drop_table('architecture_results')
    op.drop_column('projects', 'status')
