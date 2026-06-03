"""states multiselect: add states JSONB column, migrate state string to array

Revision ID: c4e7b1f8a2d9
Revises: b3f8a9c12d45
Create Date: 2026-06-03 00:00:00.000000

state and district columns are intentionally preserved in the DB (historical data).
The application layer stops reading/writing them; only states (JSONB array) is used going forward.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c4e7b1f8a2d9'
down_revision: Union[str, None] = 'b3f8a9c12d45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'executions',
        sa.Column('states', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Migrate existing single-state strings into the new array column.
    # WHERE guard prevents json_build_array(NULL) producing [null] on rows with no state.
    op.execute(
        """
        UPDATE executions
        SET states = json_build_array(state)::jsonb
        WHERE state IS NOT NULL AND state != ''
        """
    )

    # Old index referenced the state column which is no longer queried by the app
    op.drop_index(
        'idx_executions_user_state_created',
        table_name='executions',
        if_exists=True,
    )

    # GIN index enables efficient JSONB @> containment queries on states
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_executions_states_gin
        ON executions USING GIN (states)
        """
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_executions_states_gin')
    op.drop_column('executions', 'states')

    op.create_index(
        'idx_executions_user_state_created',
        'executions',
        ['created_by', 'state', 'created_at'],
        postgresql_ops={'created_at': 'DESC'},
        if_not_exists=True,
    )
