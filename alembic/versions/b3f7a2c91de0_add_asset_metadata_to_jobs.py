"""add asset metadata fields to jobs

Revision ID: b3f7a2c91de0
Revises: 06607c99f84c
Create Date: 2026-03-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f7a2c91de0'
down_revision: Union[str, Sequence[str], None] = '06607c99f84c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add source_format and preview_cache_path columns to jobs."""
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_format', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('preview_cache_path', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove source_format and preview_cache_path columns from jobs."""
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('preview_cache_path')
        batch_op.drop_column('source_format')
