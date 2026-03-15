"""Add architecture trigger fields to discovery_sessions."""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'discovery_sessions',
        sa.Column('eligible_for_architecture', sa.Boolean(), default=False, server_default='false')
    )
    op.add_column(
        'discovery_sessions',
        sa.Column('architecture_triggered', sa.Boolean(), default=False, server_default='false')
    )
    op.add_column(
        'discovery_sessions',
        sa.Column('architecture_triggered_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'discovery_sessions',
        sa.Column('architecture_trigger_status', sa.String(50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('discovery_sessions', 'architecture_trigger_status')
    op.drop_column('discovery_sessions', 'architecture_triggered_at')
    op.drop_column('discovery_sessions', 'architecture_triggered')
    op.drop_column('discovery_sessions', 'eligible_for_architecture')
