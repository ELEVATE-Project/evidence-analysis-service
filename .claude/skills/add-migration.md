# Skill: Add Alembic Migration

Alembic is the ONLY mechanism for schema changes. `Base.metadata.create_all()` is removed and must never be used.

## Migration Chain

```
(base)
  └── 7cd39d2cb21f  create initial schema (users, executions, csv_source_types)
        └── b3f8a9c12d45  add composite indexes on executions  ← HEAD
```

## Workflow

```bash
# 1. Make model changes in models/
# 2. Auto-generate
alembic revision --autogenerate -m "short_description_of_change"
# 3. REVIEW the file in db/migrations/versions/ — autogenerate is not always correct
# 4. Test upgrade
alembic upgrade head
# 5. Test downgrade (must work!)
alembic downgrade -1
alembic upgrade head
# 6. Verify: psql -c "\d tablename"
```

## Migration File Template

```python
"""short description

Revision ID: <hex>
Revises: b3f8a9c12d45
Create Date: ...
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '<hex>'
down_revision: Union[str, None] = 'b3f8a9c12d45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD COLUMN — always nullable unless there's a server_default
    op.add_column(
        'executions',
        sa.Column('new_column', sa.String(length=100), nullable=True)
    )
    # ADD NOT NULL column — requires server_default to avoid lock on existing rows
    op.add_column(
        'executions',
        sa.Column('status_code', sa.String(50), nullable=False, server_default='pending')
    )
    # ADD INDEX — always if_not_exists=True
    op.create_index(
        'ix_executions_new_column',
        'executions',
        ['new_column'],
        if_not_exists=True,
    )
    # ADD JSONB COLUMN
    op.add_column(
        'executions',
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )


def downgrade() -> None:
    op.drop_index('ix_executions_new_column', table_name='executions', if_exists=True)
    op.drop_column('executions', 'metadata')
    op.drop_column('executions', 'status_code')
    op.drop_column('executions', 'new_column')
```

## Rules

### Adding a Column
- Nullable columns: no server_default needed.
- NOT NULL columns: MUST have `server_default` to avoid table lock on large tables.
- After backfill, a separate migration can `alter_column(..., server_default=None)`.

### Adding an Index
- Always `if_not_exists=True` in `upgrade()`.
- Always `if_exists=True` in `downgrade()`.
- Composite indexes on executions must use `postgresql_ops={'created_at': 'DESC'}` for DESC columns.
- Partial indexes must use `op.execute()` with `CREATE INDEX IF NOT EXISTS ... WHERE ...`.

### Adding a Table
- Use `op.create_table()` — never raw `CREATE TABLE`.
- Include all FK constraints in `create_table()`.
- Downgrade must `op.drop_table()` in reverse dependency order.

### JSONB Columns
```python
sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
# With default:
sa.Column('config', postgresql.JSONB(astext_type=sa.Text()),
          server_default=sa.text("'{}'::jsonb"), nullable=False)
```

## Validation Checklist

- [ ] `downgrade()` is the exact reverse of `upgrade()` — tested, not empty
- [ ] NOT NULL column additions include `server_default`
- [ ] Indexes use `if_not_exists=True` / `if_exists=True`
- [ ] `down_revision` points to current HEAD before your migration
- [ ] Migration does not import ORM models (use `sa.Column` directly)
- [ ] `alembic downgrade -1 && alembic upgrade head` passes cleanly
- [ ] No `Base.metadata.create_all()` anywhere

## Anti-patterns

❌ `op.execute("CREATE TABLE ...")` — use `op.create_table()`
❌ Empty `downgrade()` function — makes rollback impossible
❌ Importing `from models.execution import Execution` inside migration
❌ Adding NOT NULL without `server_default` on a table with existing rows
❌ Changing existing migration revision IDs or content after deployment
❌ Running `alembic stamp head` to skip applying migrations (use as last resort only)

## For Existing Environments Using init_db.py (Legacy)

```bash
# If database has tables but no alembic_version:
alembic stamp 7cd39d2cb21f   # mark initial schema as applied
alembic upgrade head          # apply only remaining migrations
```
