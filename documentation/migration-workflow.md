# Database Migration Workflow

This document is the authoritative reference for all schema management on the
Evidence Analysis Service. **Alembic is the only supported mechanism for
creating or altering database schema** across every environment — local,
staging, and production.

---

## Quick Reference

| Task | Command |
|------|---------|
| Apply all pending migrations | `alembic upgrade head` |
| Check current migration state | `alembic current` |
| Show pending migrations | `alembic history --indicate-current` |
| Generate a new migration | `alembic revision --autogenerate -m "description"` |
| Rollback one step | `alembic downgrade -1` |
| Rollback to a specific revision | `alembic downgrade <revision_id>` |
| Rollback everything | `alembic downgrade base` |

---

## Migration Chain

```
(base)
  └── 7cd39d2cb21f  create initial schema
        └── b3f8a9c12d45  add composite indexes for executions
                             ← HEAD
```

---

## Fresh Environment Setup

This is the only supported onboarding path for a new developer or deployment.

```bash
# 1. Clone the repository
git clone <repository-url>
cd evidence-analysis-service-p1

# 2. Create and activate a virtual environment
python3.12 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL and JWT_SECRET_KEY

# 5. Create the database and apply all migrations (one-command)
python scripts/create_dev_db.py
# This reads DATABASE_URL from .env, creates the database if it does not
# exist, and runs `alembic upgrade head` automatically.

# 6. Seed default users and CSV source type configuration
python db/seed_data.py

# 7. Start the application
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Step 6 creates the three default users and the `project_report` CSV source type.
The application also seeds on startup automatically, but that path requires cloud
storage to be fully configured first — running `python db/seed_data.py` explicitly
ensures seed data is in place regardless of storage status.

If you prefer to run the steps manually instead of using the script:

```bash
# Create the database (the name must match DATABASE_URL in your .env)
createdb -U postgres -h localhost evidence_analysis

# Apply all migrations
alembic upgrade head

# Seed default data
python db/seed_data.py
```

### Expected tables after `alembic upgrade head`

```
alembic_version
csv_source_types
executions
users
```

---

## Applying Migrations in CI/CD and Production

Add this step **before** starting the application process:

```bash
alembic upgrade head
```

That is the complete migration step. No other database commands are required.

### Docker / Kubernetes

Run the migration as an init container or entrypoint pre-hook before the main
application container starts:

```dockerfile
# Example entrypoint.sh
#!/bin/bash
set -e
alembic upgrade head
exec uvicorn main:app --host 0.0.0.0 --port 8000
```

### Startup safety guard

The application enforces that migrations are at head before it starts. If you
attempt to start the application against a database that is behind, it will
fail immediately with:

```
RuntimeError: Database schema is out of date. Run `alembic upgrade head`
              before starting the application.
```

This prevents the application from running against a mismatched schema.

---

## Creating a New Migration

Follow this workflow any time a model is added or altered.

```bash
# 1. Make your changes to the ORM model in models/
# 2. Auto-generate the migration (Alembic diffs models vs. current schema)
alembic revision --autogenerate -m "short description of change"

# 3. Review the generated file in db/migrations/versions/
#    Verify the upgrade() and downgrade() functions are correct.
#    Autogenerate is not perfect — always review before committing.

# 4. Apply the migration locally to verify it runs cleanly
alembic upgrade head

# 5. Test the downgrade
alembic downgrade -1
alembic upgrade head   # re-apply

# 6. Commit both the model change and the migration file together
```

### Naming convention

Use short, descriptive slugs:

```
add_user_role_column
create_audit_log_table
add_idx_executions_tenant
```

### Idempotency

For index creation use `if_not_exists=True`. For table creation, use
`op.create_table` (which Alembic already makes idempotent by tracking
revision state). Avoid manual `IF NOT EXISTS` guards on table DDL — they
mask logic errors in the migration chain.

---

## Rollback Procedures

### Roll back one migration

```bash
alembic downgrade -1
```

### Roll back to a specific revision

```bash
alembic downgrade b3f8a9c12d45
```

### Roll back everything (empty database)

```bash
alembic downgrade base
```

After a rollback, re-apply with `alembic upgrade head`.

---

## Verifying Migration State

```bash
# Show the current revision applied to the database
alembic current

# Show full migration history with current marker
alembic history --indicate-current

# Show only pending (unapplied) migrations
alembic history --indicate-current | grep -v "(head)"
```

---

## What is Forbidden

| Action | Why |
|--------|-----|
| `Base.metadata.create_all()` in application code | Bypasses version history; causes drift |
| Running `python db/init_db.py` | Deprecated; same problem as above |
| Manual `CREATE TABLE` / `ALTER TABLE` in psql | Not tracked by Alembic |
| Using `python db/seed_data.py` for schema changes | It inserts rows only — schema changes require an Alembic migration |
| Environment-specific migration branches | Causes divergence between environments |

---

## Troubleshooting

### `alembic upgrade head` fails on a fresh database

**Symptom**: `relation "csv_source_types" does not exist` or similar.

**Cause**: An old migration file is present that assumed tables already existed
(created by the deprecated `init_db.py`). The migration chain was fixed in
revision `7cd39d2cb21f` — make sure you are running the current version of the
code.

**Fix**:
```bash
git pull             # ensure you have the latest migrations
alembic upgrade head
```

---

### `Target database is not up to date` at application startup

**Symptom**: Application refuses to start with a migration error.

**Fix**:
```bash
alembic upgrade head
# then restart the application
```

---

### Duplicate table / column error during upgrade

**Symptom**: `relation "users" already exists`.

**Cause**: The database was previously initialised with `init_db.py` (old
workflow) and `alembic_version` was never populated, so Alembic tries to
re-create tables that already exist.

**Fix** (one-time repair for environments set up before this migration
architecture was enforced):
```bash
# Option A: stamp the current state and apply only remaining migrations
alembic stamp 7cd39d2cb21f   # mark initial schema as applied
alembic upgrade head          # apply only newer migrations

# Option B: drop and rebuild from scratch (destroys all data)
alembic downgrade base
alembic upgrade head
```

---

### `alembic current` returns nothing

The database has never had any migrations applied.

```bash
alembic upgrade head
```

---

## Reference: Migration File Anatomy

```python
"""short description

Revision ID: <hex>
Revises: <parent_hex or None>
Create Date: ...
"""
from alembic import op
import sqlalchemy as sa

revision = '<hex>'
down_revision = '<parent_hex>'   # None for the root migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Forward schema change
    op.add_column('table', sa.Column('col', sa.String(), nullable=True))


def downgrade() -> None:
    # Exact reverse of upgrade
    op.drop_column('table', 'col')
```

Every migration **must** implement a correct `downgrade()` so rollbacks work.
