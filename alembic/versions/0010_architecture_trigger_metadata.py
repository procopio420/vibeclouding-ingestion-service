"""Add architecture_trigger_target and architecture_started_by to discovery_sessions."""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'discovery_sessions',
        sa.Column('architecture_trigger_target', sa.String(512), nullable=True)
    )
    op.add_column(
        'discovery_sessions',
        sa.Column('architecture_started_by', sa.String(50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('discovery_sessions', 'architecture_started_by')
    op.drop_column('discovery_sessions', 'architecture_trigger_target')
