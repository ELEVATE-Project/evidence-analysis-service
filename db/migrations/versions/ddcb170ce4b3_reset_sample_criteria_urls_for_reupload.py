"""reset sample_criteria_file_url so bootstrap re-uploads the updated sample CSVs

Revision ID: ddcb170ce4b3
Revises: f4a7c2e9b6d1
Create Date: 2026-08-03 00:00:00.000000

services/bootstrap.py::_upload_sample_csvs skips uploading a sample CSV whenever
its DB field (sample_criteria_file_url) is already populated, treating that as
"already uploaded in a previous startup" regardless of whether the local repo
file has since changed. public/sample-csv/projects/sample_criteria.csv and
public/sample-csv/observation/sample_criteria.csv were updated (extraction
fields added) after this environment's initial bootstrap ran, so the stale
pre-update file is still what's actually sitting in cloud storage. Clearing
the field for just these two rows makes the next startup treat them as
never-uploaded and push the current file content.

Scoped to the same (tenant_code, organization_code) pair services/bootstrap.py's
_resolve_scope() resolves to at runtime — settings.DEFAULT_TENANT_CODE /
DEFAULT_ORGANIZATION_CODE, falling back to "default" / "default_code" only when
unset — not hardcoded literals, since a deployment can and does override these
via env var (core/config.py). Also scoped to type_key IN ('project_report',
'observation') — the two source types whose sample_criteria.csv changed.
sample_input_file_url and sample_school_filter_file_url are untouched — those
files did not change.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from core.config import settings

revision: str = 'ddcb170ce4b3'
down_revision: Union[str, None] = 'f4a7c2e9b6d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _resolve_scope() -> tuple[str, str]:
    # Mirrors services/bootstrap.py::_resolve_scope() exactly, so this migration
    # targets whatever (tenant_code, organization_code) that function would
    # actually bootstrap sample CSVs for on this deployment.
    tenant_code = (settings.DEFAULT_TENANT_CODE or "default").strip() or "default"
    organization_code = (
        (settings.DEFAULT_ORGANIZATION_CODE or "default_code").strip() or "default_code"
    )
    return tenant_code, organization_code


def upgrade() -> None:
    tenant_code, organization_code = _resolve_scope()
    op.execute(
        sa.text(
            """
            UPDATE csv_source_types
            SET sample_criteria_file_url = NULL
            WHERE tenant_code = :tenant_code
              AND organization_code = :organization_code
              AND type_key IN ('project_report', 'observation')
            """
        ).bindparams(tenant_code=tenant_code, organization_code=organization_code)
    )


def downgrade() -> None:
    # sample_criteria_file_url isn't arbitrary runtime-generated data — it's always
    # "/" + the fixed cloud_path string from _SAMPLE_UPLOAD_MANIFEST in
    # services/bootstrap.py ("projects/sample_criteria.csv" /
    # "observation/sample_criteria.csv"), which every deployment uploads to
    # identically. Restore that deterministic value.
    #
    # Guarded by "IS NULL" so this only fixes rows this migration's upgrade()
    # actually cleared, not rows that were NULL because bootstrap simply hasn't
    # run yet on a brand-new environment (where the file wouldn't exist at that
    # path at all, and stamping in a URL for it would be wrong).
    tenant_code, organization_code = _resolve_scope()
    op.execute(
        sa.text(
            """
            UPDATE csv_source_types
            SET sample_criteria_file_url = '/projects/sample_criteria.csv'
            WHERE tenant_code = :tenant_code
              AND organization_code = :organization_code
              AND type_key = 'project_report'
              AND sample_criteria_file_url IS NULL
            """
        ).bindparams(tenant_code=tenant_code, organization_code=organization_code)
    )
    op.execute(
        sa.text(
            """
            UPDATE csv_source_types
            SET sample_criteria_file_url = '/observation/sample_criteria.csv'
            WHERE tenant_code = :tenant_code
              AND organization_code = :organization_code
              AND type_key = 'observation'
              AND sample_criteria_file_url IS NULL
            """
        ).bindparams(tenant_code=tenant_code, organization_code=organization_code)
    )
