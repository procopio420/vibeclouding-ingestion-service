"""Add value column to checklist_items for full extracted answers."""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'checklist_items',
        sa.Column('value', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('checklist_items', 'value')
