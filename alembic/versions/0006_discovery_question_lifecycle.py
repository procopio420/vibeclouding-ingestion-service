"""Discovery question lifecycle persistence table."""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'discovery_question_lifecycle',
        sa.Column('id', sa.String(36), primary_key=True, index=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), index=True),
        sa.Column('intent_key', sa.String(100), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, default='open'),
        sa.Column('answer_message_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('discovery_question_lifecycle')
