"""create initial schema

Revision ID: 7cd39d2cb21f
Revises:
Create Date: 2026-04-27 13:38:21.799423

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7cd39d2cb21f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True),
        sa.Column('tenant_code', sa.String(), nullable=True),
        sa.Column('organization_code', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # --- executions ---
    op.create_table(
        'executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_code', sa.String(length=100), nullable=False),
        sa.Column('organization_code', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('csv_type_id', sa.String(length=100), nullable=True),
        sa.Column('ai_model_id', sa.String(length=100), nullable=True),
        sa.Column('program_ref_id', sa.String(length=100), nullable=True),
        sa.Column('program_name', sa.String(length=255), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('criterias_mode', sa.String(length=50), nullable=True),
        sa.Column('criterias_file_url', sa.Text(), nullable=True),
        sa.Column('criterias_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('threshold_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('total_rows', sa.Integer(), nullable=True),
        sa.Column('processed_rows', sa.Integer(), nullable=True),
        sa.Column('actual_cost', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('estimated_time_seconds', sa.Integer(), nullable=True),
        sa.Column('input_file_url', sa.Text(), nullable=True),
        sa.Column('input_file_size', sa.BigInteger(), nullable=True),
        sa.Column('criterias_file_size', sa.BigInteger(), nullable=True),
        sa.Column('output_file_url', sa.Text(), nullable=True),
        sa.Column('output_file_size', sa.BigInteger(), nullable=True),
        sa.Column('worker_id', sa.String(length=100), nullable=True),
        sa.Column('error_logs', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('checkpoint_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('updated_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('upload_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('average_processing_time', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=True),
        sa.Column('notification_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_executions_created_at', 'executions', ['created_at'], unique=False)
    op.create_index('ix_executions_created_by', 'executions', ['created_by'], unique=False)
    op.create_index('ix_executions_notification_sent', 'executions', ['notification_sent'], unique=False)
    op.create_index('ix_executions_status', 'executions', ['status'], unique=False)

    # --- csv_source_types (FK to users) ---
    op.create_table(
        'csv_source_types',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_code', sa.String(length=100), nullable=False),
        sa.Column('organization_code', sa.String(length=100), nullable=False),
        sa.Column('type_key', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('has_geo', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('has_program', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('has_rubric', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('has_narrative', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('max_rows_per_upload', sa.Integer(), server_default=sa.text('10000'), nullable=True),
        sa.Column('column_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('evidence_columns', postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('evidence_context_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('available_filters', postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column(
            'question_config',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(
                "'{\"entry_options\":[{\"key\":\"UPLOAD\",\"label\":\"Upload CSV\"},"
                "{\"key\":\"COMMON\",\"label\":\"Manual Entry\"}],"
                "\"mandatory_columns\":[],\"optional_columns\":[]}'::jsonb"
            ),
            nullable=True,
        ),
        sa.Column(
            'default_thresholds',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("jsonb_build_object('relevant', 0.8, 'partial', 0.5)"),
            nullable=True,
        ),
        sa.Column('sample_input_file_url', sa.Text(), nullable=True),
        sa.Column('sample_criteria_file_url', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_code', 'organization_code', 'type_key',
            name='uq_csv_source_types_scope_type_key',
        ),
    )


def downgrade() -> None:
    op.drop_table('csv_source_types')
    op.drop_index('ix_executions_status', table_name='executions')
    op.drop_index('ix_executions_notification_sent', table_name='executions')
    op.drop_index('ix_executions_created_by', table_name='executions')
    op.drop_index('ix_executions_created_at', table_name='executions')
    op.drop_table('executions')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
