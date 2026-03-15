"""Add current_focus_key, focus_attempt_count, resolution_status to discovery_sessions."""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'discovery_sessions',
        sa.Column('current_focus_key', sa.String(100), nullable=True)
    )
    op.add_column(
        'discovery_sessions',
        sa.Column('focus_attempt_count', sa.Integer(), server_default='0')
    )
    op.add_column(
        'discovery_sessions',
        sa.Column('resolution_status', sa.String(30), nullable=True)
    )
    op.create_index(op.f('ix_discovery_sessions_current_focus_key'), 'discovery_sessions', ['current_focus_key'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_discovery_sessions_current_focus_key'), table_name='discovery_sessions')
    op.drop_column('discovery_sessions', 'resolution_status')
    op.drop_column('discovery_sessions', 'focus_attempt_count')
    op.drop_column('discovery_sessions', 'current_focus_key')
