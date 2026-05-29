# Command: Generate Migration

**Usage:** `/generate-migration <description of schema change>`

Generate a correct Alembic migration for this repository.

## What This Command Does

1. Asks for the schema change description
2. Identifies the affected model(s)
3. Generates the migration file following repository patterns
4. Validates the migration

## Pre-flight Checks

Before generating, confirm:
```bash
# Current migration head
alembic current
# Should be: b3f8a9c12d45

# Pending model changes
alembic revision --autogenerate -m "dry_run" 2>&1 | head -30
```

## Migration Template Generator

For common change types, use these patterns:

### Add column to executions
```
Change: "Add 'priority' integer column to executions, not null, default 0"

→ Generates:
op.add_column('executions', sa.Column(
    'priority', sa.Integer(), nullable=False, server_default=sa.text('0')
))
# Downgrade: op.drop_column('executions', 'priority')
```

### Add JSONB column
```
Change: "Add 'processing_config' JSONB column to executions, nullable"

→ Generates:
op.add_column('executions', sa.Column(
    'processing_config',
    postgresql.JSONB(astext_type=sa.Text()),
    nullable=True
))
```

### Add index
```
Change: "Add index on executions(tenant_code, status) for tenant-filtered queries"

→ Generates:
op.create_index(
    'idx_executions_tenant_status',
    'executions',
    ['tenant_code', 'status'],
    if_not_exists=True,
)
# Downgrade: op.drop_index(..., if_exists=True)
```

### Add table
```
Change: "Add 'execution_tags' table with execution_id FK and tag_key/tag_value columns"

→ Generates full create_table() with FKs and downgrade drop_table()
```

## Validation After Generation

```bash
# 1. Review the generated file
cat db/migrations/versions/<new_revision>.py

# 2. Apply
alembic upgrade head

# 3. Test round-trip
alembic downgrade -1
alembic upgrade head

# 4. Verify schema
psql $DATABASE_URL -c "\d <tablename>"
```

## Rules This Command Enforces

- `down_revision` points to current HEAD (`b3f8a9c12d45` or latest)
- `downgrade()` is complete — exact reverse of `upgrade()`
- NOT NULL columns have `server_default`
- All indexes use `if_not_exists=True` / `if_exists=True`
- No ORM imports inside migration file
- Uses `sa.` and `postgresql.` imports, not model classes
- Partial indexes use `op.execute()` with `CREATE INDEX IF NOT EXISTS ... WHERE ...`

## Output Format

```
Migration file: db/migrations/versions/<revision>_<description>.py
Changes:
  - upgrade(): <list of DDL operations>
  - downgrade(): <list of reverse operations>
Validation: ✓ downgrade complete | ✓ idempotent indexes | ✓ no ORM imports
```
