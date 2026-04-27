"""add sample csv url columns

Revision ID: 7cd39d2cb21f
Revises: 
Create Date: 2026-04-27 13:38:21.799423

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cd39d2cb21f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add sample CSV URL columns to csv_source_types table
    op.add_column('csv_source_types', sa.Column('sample_input_file_url', sa.Text(), nullable=True))
    op.add_column('csv_source_types', sa.Column('sample_criteria_file_url', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove sample CSV URL columns from csv_source_types table
    op.drop_column('csv_source_types', 'sample_criteria_file_url')
    op.drop_column('csv_source_types', 'sample_input_file_url')
