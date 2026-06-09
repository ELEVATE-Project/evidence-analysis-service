# Database Schema Context

## Tables

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | String PK | `str(uuid.uuid4())` — not UUID type |
| username | String UNIQUE NOT NULL | indexed |
| email | String UNIQUE NOT NULL | indexed |
| hashed_password | String NOT NULL | bcrypt rounds=12 |
| full_name | String | nullable |
| is_active | Boolean | default True |
| is_superuser | Boolean | default False |
| tenant_code | String | nullable |
| organization_code | String | nullable |
| created_at | DateTime(tz) | server_default=now() |
| updated_at | DateTime(tz) | onupdate=now() |

### `executions`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | `uuid.uuid4()` (PostgreSQL UUID type) |
| tenant_code | String(100) NOT NULL | multi-tenancy scope |
| organization_code | String(100) NOT NULL | multi-tenancy scope |
| name | String(255) NOT NULL | |
| csv_type_id | String(100) | FK-like to csv_source_types.type_key (soft) |
| ai_model_id | String(100) | e.g. "gemini-2.5-flash" |
| program_ref_id | String(100) | external program reference |
| program_name | String(255) | |
| state | String(50) | geographic scope |
| district | String(100) | |
| criterias_mode | String(50) | "UPLOAD" or "COMMON" |
| criterias_file_url | Text | absolute cloud path |
| criterias_config | JSONB | criteria configuration |
| threshold_config | JSONB | relevance/partial thresholds |
| **status** | String(50) NOT NULL indexed | **queued→in_progress→completed/failed** |
| failure_reason | Text | human-readable failure summary |
| total_rows | Integer | total evidence rows |
| processed_rows | Integer | rows completed |
| actual_cost | Numeric(10,4) | Gemini API cost |
| estimated_cost | Numeric(10,4) | pre-run estimate |
| estimated_time_seconds | Integer | |
| input_file_url | Text | absolute cloud path |
| input_file_size | BigInteger | bytes |
| criterias_file_size | BigInteger | bytes |
| output_file_url | Text | absolute cloud path |
| output_file_size | BigInteger | bytes |
| worker_id | String(100) | Celery worker hostname |
| error_logs | Text | full subprocess stderr |
| retry_count | Integer | Celery retry count |
| checkpoint_data | JSONB | resume state |
| created_by | String(100) indexed | user.id |
| updated_by | String(100) | |
| created_at | DateTime(tz) indexed | server_default=now() |
| updated_at | DateTime(tz) | onupdate=now() |
| completed_at | DateTime(tz) | |
| upload_completed_at | DateTime(tz) | when all files uploaded |
| processing_started_at | DateTime(tz) | |
| processing_completed_at | DateTime(tz) | |
| average_processing_time | Numeric(10,2) | seconds per row |
| notification_sent | Boolean indexed | |
| notification_sent_at | DateTime(tz) | |

### `csv_source_types`
| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK autoincrement | |
| tenant_code | String(100) NOT NULL | |
| organization_code | String(100) NOT NULL | |
| type_key | String(100) NOT NULL | e.g. "project_report" |
| display_name | String(255) NOT NULL | |
| description | Text | |
| has_geo | Boolean NOT NULL | has state/district fields |
| has_program | Boolean NOT NULL | has program ID/name fields |
| has_rubric | Boolean NOT NULL | |
| has_narrative | Boolean NOT NULL | |
| max_rows_per_upload | Integer | server_default=10000 |
| column_mappings | JSONB NOT NULL | column name mappings |
| evidence_columns | JSONB NOT NULL | evidence column configs |
| evidence_context_config | JSONB NOT NULL | context extraction rules |
| available_filters | JSONB | filter field list |
| question_config | JSONB | entry options, mandatory columns |
| default_thresholds | JSONB | {relevant: 0.8, partial: 0.5} |
| sample_input_file_url | Text | cloud path (set by bootstrap) |
| sample_criteria_file_url | Text | cloud path (set by bootstrap) |
| is_active | Boolean NOT NULL | server_default=true |
| created_by | String(255) FK→users.id | |
| updated_by | String(255) FK→users.id | |
| created_at | DateTime(tz) NOT NULL | server_default=now() |
| updated_at | DateTime(tz) NOT NULL | server_default=now() |

**Unique constraint:** `(tenant_code, organization_code, type_key)` — `uq_csv_source_types_scope_type_key`

## Indexes (beyond column-level)

On `executions`:
| Index | Columns | Purpose |
|-------|---------|---------|
| `ix_executions_status` | status | status filter |
| `ix_executions_created_by` | created_by | user filter |
| `ix_executions_created_at` | created_at | sort |
| `ix_executions_notification_sent` | notification_sent | notification job |
| `idx_executions_user_created` | created_by, created_at DESC | user list sorted |
| `idx_executions_user_status_created` | created_by, status, created_at DESC | user+status filter |
| `idx_executions_user_state_created` | created_by, state, created_at DESC | user+state filter |
| `idx_executions_in_progress` | created_by, created_at DESC WHERE status IN (...) | checkpoint polling |

## Migration Chain

```
alembic_version
  └── 7cd39d2cb21f  (create initial schema — users, executions, csv_source_types)
        └── b3f8a9c12d45  (add composite indexes for executions)  ← HEAD
```

## Seed Data (default scope)

**Users** (`tenant_code="default"`, `organization_code="default_code"`):
- `admin` / `admin123` — superuser
- `program_designer` / `user123`
- `analyst` / `user123`

**CsvSourceType** (`type_key="project_report"`):
- `has_geo=True`, `has_program=True`
- `max_rows_per_upload=10000`
- `default_thresholds={"relevant": 0.7, "partial": 0.5}`
- Sample files uploaded to cloud at bootstrap

## Connection Pool

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
```
Max concurrent connections: 30 (10 + 20 overflow).
