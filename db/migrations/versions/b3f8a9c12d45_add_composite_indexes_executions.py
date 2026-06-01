"""add composite indexes for executions list query performance

Revision ID: b3f8a9c12d45
Revises: 7cd39d2cb21f
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3f8a9c12d45'
down_revision: Union[str, None] = '7cd39d2cb21f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite indexes for list_executions() query patterns
    # Using CONCURRENTLY-equivalent: op.create_index with postgresql_concurrently
    op.create_index(
        'idx_executions_user_created',
        'executions',
        ['created_by', 'created_at'],
        postgresql_ops={'created_at': 'DESC'},
        if_not_exists=True,
    )
    op.create_index(
        'idx_executions_user_status_created',
        'executions',
        ['created_by', 'status', 'created_at'],
        postgresql_ops={'created_at': 'DESC'},
        if_not_exists=True,
    )
    op.create_index(
        'idx_executions_user_state_created',
        'executions',
        ['created_by', 'state', 'created_at'],
        postgresql_ops={'created_at': 'DESC'},
        if_not_exists=True,
    )
    # Partial index: only in-progress/queued executions (used by checkpoint polling)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_executions_in_progress
        ON executions(created_by, created_at DESC)
        WHERE status IN ('in_progress', 'queued', 'running')
        """
    )


def downgrade() -> None:
    op.drop_index('idx_executions_in_progress', table_name='executions', if_exists=True)
    op.drop_index('idx_executions_user_state_created', table_name='executions', if_exists=True)
    op.drop_index('idx_executions_user_status_created', table_name='executions', if_exists=True)
    op.drop_index('idx_executions_user_created', table_name='executions', if_exists=True)
