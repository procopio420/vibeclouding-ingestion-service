"""Add revision_decision to projects."""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'projects',
        sa.Column('revision_decision', sa.String(50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('projects', 'revision_decision')
