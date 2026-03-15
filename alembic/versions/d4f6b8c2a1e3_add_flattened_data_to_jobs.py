"""add flattened job payload fields

Revision ID: d4f6b8c2a1e3
Revises: b3f7a2c91de0
Create Date: 2026-03-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f6b8c2a1e3'
down_revision: Union[str, Sequence[str], None] = 'b3f7a2c91de0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add flattened_data and flattening_status columns to jobs."""
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('flattened_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('flattening_status', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove flattened_data and flattening_status columns from jobs."""
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('flattening_status')
        batch_op.drop_column('flattened_data')