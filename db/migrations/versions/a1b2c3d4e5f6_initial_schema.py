"""initial schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('username', sa.String(), nullable=False, unique=True),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('is_superuser', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('tenant_code', sa.String(), nullable=True),
        sa.Column('organization_code', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])

    op.create_table(
        'csv_source_types',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tenant_code', sa.String(100), nullable=False),
        sa.Column('organization_code', sa.String(100), nullable=False),
        sa.Column('type_key', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('has_geo', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_program', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_rubric', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_narrative', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('max_rows_per_upload', sa.Integer(), nullable=True, server_default=sa.text('10000')),
        sa.Column('column_mappings', JSONB(), nullable=False),
        sa.Column('evidence_columns', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('evidence_context_config', JSONB(), nullable=False),
        sa.Column('available_filters', JSONB(), nullable=True, server_default=sa.text("'[]'::jsonb")),
        sa.Column('question_config', JSONB(), nullable=True),
        sa.Column('default_thresholds', JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_by', sa.String(255), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_by', sa.String(255), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_code', 'organization_code', 'type_key', name='uq_csv_source_types_scope_type_key'),
    )

    op.create_table(
        'executions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_code', sa.String(100), nullable=False),
        sa.Column('organization_code', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('csv_type_id', sa.String(100), nullable=True),
        sa.Column('ai_model_id', sa.String(100), nullable=True),
        sa.Column('program_ref_id', sa.String(100), nullable=True),
        sa.Column('program_name', sa.String(255), nullable=True),
        sa.Column('state', sa.String(50), nullable=True),
        sa.Column('district', sa.String(100), nullable=True),
        sa.Column('criterias_mode', sa.String(50), nullable=True),
        sa.Column('criterias_file_url', sa.Text(), nullable=True),
        sa.Column('criterias_config', JSONB(), nullable=True),
        sa.Column('threshold_config', JSONB(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued'),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('total_rows', sa.Integer(), nullable=True),
        sa.Column('processed_rows', sa.Integer(), server_default='0'),
        sa.Column('actual_cost', sa.Numeric(10, 4), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(10, 4), nullable=True),
        sa.Column('estimated_time_seconds', sa.Integer(), nullable=True),
        sa.Column('input_file_url', sa.Text(), nullable=True),
        sa.Column('input_file_size', sa.BigInteger(), nullable=True),
        sa.Column('criterias_file_size', sa.BigInteger(), nullable=True),
        sa.Column('output_file_url', sa.Text(), nullable=True),
        sa.Column('output_file_size', sa.BigInteger(), nullable=True),
        sa.Column('worker_id', sa.String(100), nullable=True),
        sa.Column('error_logs', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('checkpoint_data', JSONB(), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('upload_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('average_processing_time', sa.Numeric(10, 2), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('notification_sent_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_executions_status', 'executions', ['status'])
    op.create_index('ix_executions_created_by', 'executions', ['created_by'])
    op.create_index('ix_executions_created_at', 'executions', ['created_at'])
    op.create_index('ix_executions_notification_sent', 'executions', ['notification_sent'])


def downgrade() -> None:
    op.drop_table('executions')
    op.drop_table('csv_source_types')
    op.drop_table('users')
