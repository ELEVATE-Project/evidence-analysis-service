"""add school_filter_config and sample_school_filter_file_url to csv_source_types

Revision ID: 863e42f58dcb
Revises: 3e798d60d93e, a1b2c3d4e5f6
Create Date: 2026-07-10 00:00:00.000000

Merges the two heads left unreconciled after merging evidence-type-filter's migration
(a1b2c3d4e5f6) into this branch, which had already diverged with its own school-filter
migration (3e798d60d93e) off the same parent (c4e7b1f8a2d9).

Combines what were two separate csv_source_types-only migrations (sample_school_filter_file_url,
school_filter_config) into one, matching the one-migration-per-table convention used elsewhere
in this chain (e.g. a1b2c3d4e5f6, 5f30ba3da9ec) — the school-filter work had drifted from that
by splitting a single table's changes across two files.

school_filter_config moves the school-filter required-column name out of core/constants.py
(Python code, required a deploy to change) and into a DB-driven column, following the same
pattern as evidence_types_config. server_default backfills existing rows with the current
hardcoded value so this is a zero-downtime, non-breaking addition.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '863e42f58dcb'
down_revision: Union[str, Sequence[str], None] = ('3e798d60d93e', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_SCHOOL_FILTER_CONFIG_JSON = '{"required_column": "School ID"}'


def upgrade() -> None:
    op.add_column(
        'csv_source_types',
        sa.Column('sample_school_filter_file_url', sa.Text(), nullable=True),
    )
    op.add_column(
        'csv_source_types',
        sa.Column(
            'school_filter_config',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text(f"'{_DEFAULT_SCHOOL_FILTER_CONFIG_JSON}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column('csv_source_types', 'school_filter_config')
    op.drop_column('csv_source_types', 'sample_school_filter_file_url')
