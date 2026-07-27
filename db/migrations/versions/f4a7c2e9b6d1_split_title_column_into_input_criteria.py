"""split evidence_context_config.title_column into input_csv_column/criteria_csv_column

Revision ID: f4a7c2e9b6d1
Revises: 863e42f58dcb
Create Date: 2026-07-27 00:00:00.000000

Backfills already-seeded csv_source_types rows to the new decoupled config shape.
seed_data.py only inserts missing type_keys — it never updates existing rows — so any
environment where project_report/observation were already seeded (with the old,
single-column title_column key) would silently break task matching once this deploy's
code (which only reads input_csv_column/criteria_csv_column) goes live, unless this data
is backfilled here.

Split, not a plain rename, because the two new fields can carry different values:
- input_csv_column: the real, externally-generated input CSV's own task column — must
  keep the exact value title_column had, since that's what real uploaded files use.
- criteria_csv_column: our own criteria file's join-key column. For the default tenant's
  project_report/observation specifically, this becomes "context" (the agreed rename,
  already reflected in seed_data.py, public/sample-csv/*, and the running dev DB). For any
  OTHER tenant still on the old shape, it's set to the SAME old value as input_csv_column
  — preserving their existing behavior exactly, since renaming their criteria column to
  "context" was never a decision made on their behalf.

Also nulls sample_criteria_file_url for affected rows so services/bootstrap.py's existing
"upload if NULL" logic re-uploads the corrected (renamed) sample criteria CSV on next
startup, instead of leaving the stale pre-rename file sitting in cloud storage indefinitely
(bootstrap has no other way to detect the local sample file changed).

WHERE evidence_context_config ? 'title_column' makes this idempotent and self-limiting —
only rows still on the old shape are touched; the default tenant's already-hand-patched
rows (from mid-session direct DB work) no longer match and are correctly skipped.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f4a7c2e9b6d1'
down_revision: Union[str, None] = '863e42f58dcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_TENANT_CODE = 'default'
_DEFAULT_ORGANIZATION_CODE = 'default_code'
_OLD_PLACEHOLDER = 'evidence_context_config.title_column'
_NEW_PLACEHOLDER = 'evidence_context_config.criteria_csv_column'


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            UPDATE csv_source_types
            SET evidence_context_config = (evidence_context_config - 'title_column') || jsonb_build_object(
                    'input_csv_column', evidence_context_config->>'title_column',
                    'criteria_csv_column',
                    CASE
                        WHEN tenant_code = :default_tenant AND organization_code = :default_org
                            THEN 'context'
                        ELSE evidence_context_config->>'title_column'
                    END
                ),
                sample_criteria_file_url = NULL
            WHERE evidence_context_config ? 'title_column'
            """
        ),
        {"default_tenant": _DEFAULT_TENANT_CODE, "default_org": _DEFAULT_ORGANIZATION_CODE},
    )

    # Fix the mandatory_columns placeholder string in the same rows. Guarded separately
    # since question_config is nullable and mandatory_columns may be absent/non-array —
    # jsonb_set on a row missing the path would silently no-op rather than error, but the
    # explicit existence check keeps this migration's intent obvious.
    conn.execute(
        sa.text(
            """
            UPDATE csv_source_types
            SET question_config = jsonb_set(
                question_config,
                '{mandatory_columns}',
                (
                    SELECT jsonb_agg(
                        CASE WHEN elem = to_jsonb(CAST(:old_placeholder AS text))
                             THEN to_jsonb(CAST(:new_placeholder AS text))
                             ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(question_config->'mandatory_columns') AS elem
                )
            )
            WHERE question_config ? 'mandatory_columns'
              AND jsonb_typeof(question_config->'mandatory_columns') = 'array'
              AND question_config->'mandatory_columns' @> jsonb_build_array(:old_placeholder)
            """
        ),
        {"old_placeholder": _OLD_PLACEHOLDER, "new_placeholder": _NEW_PLACEHOLDER},
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Restore title_column from input_csv_column (not criteria_csv_column) — that's the
    # value real uploaded input files actually use; criteria_csv_column may have been
    # renamed to "context" for the default tenant and would break matching if restored
    # into the single shared field. sample_criteria_file_url is left NULL rather than
    # restored to its pre-migration value (not recorded here) — bootstrap.py will
    # re-upload whichever sample_criteria.csv the reverted code/files have on next start,
    # which is correct either direction.
    conn.execute(
        sa.text(
            """
            UPDATE csv_source_types
            SET evidence_context_config = (evidence_context_config - 'input_csv_column' - 'criteria_csv_column')
                || jsonb_build_object('title_column', evidence_context_config->>'input_csv_column')
            WHERE evidence_context_config ? 'input_csv_column'
              AND evidence_context_config ? 'criteria_csv_column'
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE csv_source_types
            SET question_config = jsonb_set(
                question_config,
                '{mandatory_columns}',
                (
                    SELECT jsonb_agg(
                        CASE WHEN elem = to_jsonb(CAST(:new_placeholder AS text))
                             THEN to_jsonb(CAST(:old_placeholder AS text))
                             ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(question_config->'mandatory_columns') AS elem
                )
            )
            WHERE question_config ? 'mandatory_columns'
              AND jsonb_typeof(question_config->'mandatory_columns') = 'array'
              AND question_config->'mandatory_columns' @> jsonb_build_array(:new_placeholder)
            """
        ),
        {"old_placeholder": _OLD_PLACEHOLDER, "new_placeholder": _NEW_PLACEHOLDER},
    )
