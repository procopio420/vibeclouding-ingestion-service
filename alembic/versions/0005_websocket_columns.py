"""Add client_id and run_id to chat_messages.

This migration adds WebSocket-related columns for tracking
client connections and assistant runs.
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('chat_messages', sa.Column('client_id', sa.String(36), nullable=True, index=True))
    op.add_column('chat_messages', sa.Column('run_id', sa.String(36), nullable=True, index=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'run_id')
    op.drop_column('chat_messages', 'client_id')
