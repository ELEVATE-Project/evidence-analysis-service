"""add sample csv url columns

Revision ID: 7cd39d2cb21f
Revises: 
Create Date: 2026-04-27 13:38:21.799423

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '7cd39d2cb21f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add sample CSV URL columns to csv_source_types table.
    Idempotent: checks if columns exist before adding them.
    This handles cases where Base.metadata.create_all() already created these columns.
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('csv_source_types')}
    
    # Only add columns if they don't already exist
    if 'sample_input_file_url' not in existing_columns:
        op.add_column('csv_source_types', sa.Column('sample_input_file_url', sa.Text(), nullable=True))
    
    if 'sample_criteria_file_url' not in existing_columns:
        op.add_column('csv_source_types', sa.Column('sample_criteria_file_url', sa.Text(), nullable=True))


def downgrade() -> None:
    """
    Remove sample CSV URL columns from csv_source_types table.
    Idempotent: checks if columns exist before dropping them.
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('csv_source_types')}
    
    # Only drop columns if they exist
    if 'sample_criteria_file_url' in existing_columns:
        op.drop_column('csv_source_types', 'sample_criteria_file_url')
    
    if 'sample_input_file_url' in existing_columns:
        op.drop_column('csv_source_types', 'sample_input_file_url')
