# Evidence Analysis Service — Phase 1

## What This System Does

The Evidence Analysis Service is an AI-powered platform that processes CSV-based educational evidence data for PBL (Project-Based Learning) programs in India. It automates the evaluation of classroom evidence (photographs, documents, observation data) against defined pedagogical criteria using Google Gemini AI, producing scored relevance reports for program managers and analysts.

**Core user journey:**
1. Upload an evidence CSV (rows contain field observation data + image URLs)
2. Upload a criteria CSV (questions mapped to task identifiers)
3. Run AI analysis — Gemini evaluates each evidence item against each criterion
4. Download an output CSV with relevance scores, tags, and reasoning per evidence row

**Business context:** Multi-tenant SaaS for educational NGOs running PBL programs. Each tenant + organization combination is isolated. Default seed is for "default/default_code" scope.

---

## Architecture Overview

```
┌──────────────┐    JWT Bearer     ┌──────────────────────────────────┐
│   React UI   │ ───────────────▶  │   FastAPI (main.py, port 8000)   │
│  (Port 5173) │ ◀─────────────── │   Routers → Services → ORM       │
└──────────────┘   Signed URLs    └──────────────────────────────────┘
                                           │  DB (SQLAlchemy)    │  Cloud Storage
                                           ▼                     ▼
                                   ┌──────────────┐    ┌─────────────────┐
                                   │  PostgreSQL  │    │  GCP / AWS S3   │
                                   │  (Port 5432) │    │  (cloud-only)   │
                                   └──────────────┘    └─────────────────┘
                                           │
                         ┌─────────────────┴──────────────────┐
                         ▼                                     ▼
                  ┌─────────────┐                    ┌──────────────────┐
                  │  RabbitMQ   │ ──Celery task──▶   │  Celery Worker   │
                  │  (AMQP)     │                    │  (subprocess AI) │
                  └─────────────┘                    └──────────────────┘
```

### Layer Responsibilities

| Layer | Path | Responsibility |
|-------|------|---------------|
| **Routers** | `routers/` | HTTP binding only. Parse request, call service, return response. No business logic. |
| **Services** | `services/` | All business logic, DB queries, validation, orchestration. |
| **Models (ORM)** | `models/*.py` (non-schema) | SQLAlchemy table definitions only. No methods. |
| **Schemas** | `models/schemas.py`, `models/entity_schemas.py` | Pydantic DTOs for API boundaries. |
| **Core** | `core/` | Config (Pydantic settings), DI wiring. |
| **DB** | `db/` | Engine, session factory, seed data, Alembic migrations. |
| **Clients** | `clients/` | External HTTP API clients. Isolated, typed, retryable. |
| **Scripts** | `scripts/` | Standalone subprocess scripts. No FastAPI dependencies. |

### Critical Flows

**Execution lifecycle states:** `queued → in_progress → completed | failed`

**File upload flow (signed URL pattern):**
```
POST /executions/{id}/files/{type}/upload-url  →  StorageService.generate_upload_url()
  → returns: {url, method, headers, expires_in_seconds}
Frontend PUT directly to cloud storage
POST /executions/{id}/files/{type}/complete    →  StorageService.get_file_metadata()
  → records file path + size in DB
```

**Execution processing (subprocess pipeline):**
```
POST /executions/{id}/run
  → BackgroundWorker.submit_job()     # tries Celery, falls back to ThreadPoolExecutor
    → process_execution(id)           # execution_processor.py
      → downloads CSVs from cloud storage
      → runs scripts/pre-processor/1-pre-processor.py (subprocess)
      → runs scripts/processor/1-main-parallel-script.py (subprocess, parallel)
      → uploads output CSV to cloud storage
      → sends completion email
```

**Startup lifecycle (main.py lifespan):**
```
_assert_migrations_current()           # fail fast if DB is behind
seed_default_users(db)                 # idempotent
seed_default_csv_source_types(db)      # idempotent
await run_bootstrap(db)                # deep cloud storage validation + sample upload
BackgroundWorker()                     # init Celery, thread pool fallback
```

### Multi-tenancy

Every query MUST be scoped by `(tenant_code, organization_code)`. The resolution pattern is:
```python
tenant_code = current_user.tenant_code or settings.DEFAULT_TENANT_CODE
organization_code = current_user.organization_code or settings.DEFAULT_ORGANIZATION_CODE
```
Missing scope is always a 500 error, not a silent fallback to empty.

### Storage Architecture

- **Cloud-only**: GCP or AWS S3. No local filesystem fallback.
- **Absolute paths**: All file paths stored as `/user_id/exec_id/filename.csv` (leading slash, no bucket prefix)
- **Signed URLs**: All downloads go through `generate_download_url()`. Never expose direct object URLs.
- **`StorageService`**: Instantiated per request. `asyncio.to_thread()` wraps all SDK calls.

### Gemini Multi-Key Rotation

Up to 3 API keys resolved from `GEMINI_API_KEY_1..3`. Key resolution in `services/gemini_runtime.py`. The processor scripts inherit keys via `build_gemini_env_overrides()` — **never pass keys directly to subprocesses via CLI args** (visible in `ps`).

---

## Repository Rules

### Layer Boundaries (never violate)

1. **Routers never query the database.** They call service methods only.
2. **Routers never import ORM models directly.** They import from `models/schemas.py`.
3. **Services own all DB access.** One `Session` per request, injected by FastAPI DI.
4. **Scripts are standalone.** They must not import FastAPI, routers, or use `app`.
5. **Models (ORM) have no methods.** No business logic in SQLAlchemy model classes.
6. **`core/config.py` is read-only settings.** No mutation after startup.

### Import Rules

```python
# ALLOWED: router → service → model/schema/client
from models.schemas import ExecutionResponse     # ✓
from services.execution_service import ExecutionService  # ✓
from db.database import get_db                   # ✓

# FORBIDDEN in routers:
from models.execution import Execution           # ✗ — ORM in router
from db.database import SessionLocal             # ✗ — raw session in router
```

### Database Rules

- **Schema changes via Alembic only.** `Base.metadata.create_all()` is removed and forbidden.
- **Never call `db.commit()` in a router.** Commits happen in services.
- **Always include `db.rollback()` on exception paths** that mutate state.
- **Do not use `db.execute()` with raw SQL** unless Alembic migration or seeding.
- **All queries scoped by tenant.** No cross-tenant data access.
- Migration chain: `7cd39d2cb21f` (create schema) → `b3f8a9c12d45` (indexes)

### Multi-tenancy Rules

- Never return data without `tenant_code + organization_code` filter.
- `_resolve_scope(current_user)` helper in `ExecutionService` is the canonical pattern.
- Default scope: `"default" / "default_code"` (for seed data only).

### Storage Rules

- `CLOUD_STORAGE_PROVIDER` must be `"gcp"` or `"aws"`. No other values.
- All uploads/downloads go through `StorageService` methods.
- Never construct cloud URLs manually (no `f"gs://{bucket}/..."` in service code).
- Signed URL expiry: upload = 900s, download = 600s (from settings).
- File paths: use `storage_service.build_execution_file_path(user_id, exec_id, filename)`.

### Validation Rules

- **Pydantic schemas at API boundary** — request body, query params, response model.
- **Service-level validation** for business rules (e.g., execution state transitions).
- Never validate at the router layer (beyond Pydantic auto-validation).
- CSV validation uses `_extract_headers_and_row_count()` before any processing.

---

## Coding Standards

### Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Functions/methods | `snake_case` | `get_execution()` |
| Private helpers | `_snake_case` | `_resolve_scope()` |
| Classes | `PascalCase` | `ExecutionService` |
| Constants | `SCREAMING_SNAKE` | `_DEFAULT_ESTIMATED_COST_PER_ROW` |
| Pydantic models | `PascalCase` | `ExecutionCreateRequest` |
| ORM models | `PascalCase` | `Execution`, `CsvSourceType` |
| DB field: status values | lowercase string | `"queued"`, `"in_progress"`, `"completed"`, `"failed"` |

### Async Standards

- FastAPI route handlers: always `async def`
- Service methods that call cloud storage: `async def`, use `await`
- Service methods that are DB-only: use `def` (SQLAlchemy is sync)
- **Never use `asyncio.run()` inside an async context** — use `await` or `asyncio.to_thread()`
- Blocking SDK calls (boto3, GCS): MUST be wrapped in `asyncio.to_thread()`
- Background processor uses `asyncio.run(coro)` explicitly (it runs in a thread)

### Logging Standards

```python
logger = logging.getLogger(__name__)   # per module, at module level

# Structured key=value format for machine parsing
logger.info("execution_started  id=%s  tenant=%s  rows=%d", exec_id, tenant, rows)
logger.warning("retry_scheduled  attempt=%d/%d  reason=%s", n, max, reason)
logger.error("upload_failed  key=%s  code=%s  error=%s", key, code, exc)

# Never log: passwords, JWT secrets, API keys, full signed URLs
# Never use f-strings in logger calls (use % formatting)
```

### Exception Standards

```python
# Domain exceptions: inherit from base, carry structured data
class StorageUploadError(StorageError): ...
class EntityServiceError(Exception):
    def __init__(self, message, *, code, status_code, details=None): ...

# HTTP exceptions: only in routers or service methods called directly by routers
raise HTTPException(status_code=404, detail="Execution not found")

# Never: bare `raise Exception("message")`
# Never: silently swallow exceptions with empty except blocks
# Always: log before raising in service layer
```

### API Response Standards

```python
# Standard routes: use Pydantic response_model
@router.get("/{id}", response_model=ExecutionResponse)

# Entity/config routes: use StandardAPIResponse envelope
return JSONResponse(
    status_code=200,
    content=StandardAPIResponse(success=True, data=items, meta={...}).model_dump(exclude_none=True)
)

# HTTP errors: always include EXECUTION_COMMON_ERROR_RESPONSES in responses={}
# HTTP 404: use detail string matching frontend expectations exactly
```

### Type Safety

- Use `from __future__ import annotations` at top of service files
- Return types on all public service methods
- `Optional[T]` not `T | None` for compatibility (Python 3.12 allows both; keep consistent)
- `Union[str, None]` only in migration files for Alembic compatibility

---

## AI Behaviour Rules

When generating or modifying code in this repository:

1. **Preserve architecture patterns.** Routers stay thin. Services own logic. Do not introduce business logic in routes.

2. **Never bypass migrations.** Schema changes require Alembic revision. Never use `create_all()`, `drop_all()`, or raw `CREATE TABLE`.

3. **Maintain multi-tenancy.** Every new DB query that returns user data MUST include `tenant_code` and `organization_code` filters.

4. **Cloud storage only.** Do not add local file storage paths, `os.path` file writes for persistence, or filesystem caching. Use `StorageService`.

5. **Match logging style.** Use `%s` formatting, `key=value` structured format, `logging.getLogger(__name__)`.

6. **Do not create new global state.** New singletons must follow the pattern in `core/dependencies.py` (module-level `Optional[T]`, initialized in `main.py` lifespan or lazily in the getter).

7. **No raw SQL in services.** Use SQLAlchemy ORM. Raw SQL belongs only in migrations.

8. **Keep Alembic migrations idempotent.** Use `if_not_exists=True` for indexes. Test both `upgrade()` and `downgrade()`.

9. **Do not add new subprocesses without updating `ExecutionWorkspace`.** New script paths must be configurable via settings.

10. **Gemini keys are always resolved via `get_gemini_tokens()`.** Never read `GEMINI_API_KEY_1` directly in new code.

11. **When adding a new service:** create a `get_<name>_service()` function in `core/dependencies.py`, add a type alias, and initialize in lifespan if it has startup requirements.

12. **Never regenerate existing migration files.** Changing migration content after it's deployed is a production data-loss risk.

---

## Development Workflows

### Fresh Environment Setup

```bash
cp .env.example .env          # fill in DATABASE_URL, JWT_SECRET_KEY, cloud credentials
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
createdb evidence_analysis
alembic upgrade head           # creates all tables — THE ONLY schema path
uvicorn main:app --reload      # seeds data + validates cloud storage on first start
```

### Adding a Migration

```bash
# 1. Make model changes in models/
# 2. Auto-generate migration
alembic revision --autogenerate -m "short_description"
# 3. REVIEW the generated file in db/migrations/versions/
# 4. Verify upgrade() and downgrade() are correct
# 5. Apply and test
alembic upgrade head
alembic downgrade -1 && alembic upgrade head    # test round-trip
```

### Starting All Services (Docker)

```bash
docker-compose up -d
# Order: postgres → rabbitmq → backend → celery-worker → frontend
# Backend runs: alembic upgrade head && python scripts/upload_sample_csvs.py && uvicorn
# Monitor: docker-compose logs -f backend celery-worker
```

### Running the Celery Worker (native)

```bash
source venv/bin/activate
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
```

### Testing an Execution End-to-End (manual)

```bash
# 1. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin&password=admin123"

# 2. Create execution
# 3. Get upload URL, PUT file to cloud
# 4. Complete upload
# 5. Validate
# 6. Start
# 7. Poll status: GET /api/v1/executions/{id}
# 8. Download report
```

---

## Important Files

| File | Why It Matters |
|------|---------------|
| `main.py` | Startup lifecycle: migration check → seed → bootstrap → worker init |
| `core/config.py` | All environment settings — start here for any env var |
| `core/dependencies.py` | DI wiring — add new service dependencies here |
| `services/execution_service.py` | 800+ line core service — most business logic lives here |
| `services/execution_processor.py` | Subprocess pipeline runner — AI processing implementation |
| `services/storage_service.py` | Cloud storage abstraction — all file I/O goes through this |
| `services/bootstrap.py` | Startup validation + sample CSV upload |
| `services/gemini_runtime.py` | Gemini key/model resolution — always use this, never raw env access |
| `db/migrations/versions/7cd39d2cb21f_create_initial_schema.py` | Root migration — all tables |
| `db/migrations/versions/b3f8a9c12d45_add_composite_indexes_executions.py` | Performance indexes |
| `db/seed_data.py` | Default users + CSV source type — runs on every startup |
| `models/schemas.py` | All Pydantic DTOs — 470 lines |
| `env_variables.py` | Environment validation table with required_if logic |
| `alembic.ini` | Alembic config — script_location = db/migrations |
| `docker-compose.yml` | Full local stack — postgres, rabbitmq, redis, backend, celery, frontend |
| `scripts/processor/1-main-parallel-script.py` | Actual Gemini AI processing |
| `public/sample-csv/projects/` | Sample CSV files uploaded to cloud on startup |

---

## Common Mistakes to Avoid

### Schema Management
- ❌ `Base.metadata.create_all()` anywhere — use `alembic upgrade head`
- ❌ Editing existing migration file content after deployment
- ❌ Missing `downgrade()` implementation in new migrations
- ❌ Adding NOT NULL column without a server_default in migration

### Multi-tenancy
- ❌ Returning all executions without `WHERE tenant_code = ? AND organization_code = ?`
- ❌ Hardcoding `"default"` tenant instead of reading from current_user
- ❌ Using `settings.DEFAULT_TENANT_CODE` in service logic (only valid for seed/bootstrap)

### Async / Blocking I/O
- ❌ Calling boto3/GCS SDK methods directly inside `async def` without `asyncio.to_thread()`
- ❌ `asyncio.run()` inside an async function (use `await` or `asyncio.to_thread()`)
- ❌ Long CPU-bound work in a route handler without offloading to background

### Storage
- ❌ Constructing cloud paths manually: `f"gs://{bucket}/{key}"`
- ❌ Storing absolute OS paths (`/tmp/...`) in the database
- ❌ Passing `CLOUD_STORAGE_PROVIDER=local` — only `gcp` and `aws` supported
- ❌ Calling `StorageService` upload/download without `await`

### Error Handling
- ❌ `except Exception: pass` — always log and re-raise or return None explicitly
- ❌ Catching `ClientError` and returning `None` without checking if it's truly 404
- ❌ Raising `HTTPException` inside `execution_processor.py` (no FastAPI context there)

### Credentials
- ❌ Logging JWT tokens, API keys, or signed URLs
- ❌ Passing Gemini keys as CLI args to subprocesses (visible in `ps`)
- ❌ Reading `GEMINI_API_KEY_1` directly — use `get_gemini_tokens()`

### Dependency Injection
- ❌ Instantiating services directly in route handlers: `svc = ExecutionService(db, worker)`
- ❌ Using `SessionLocal()` inside a route handler — use `Depends(get_db)`
- ❌ Forgetting to add new singleton services to `core/dependencies.py`

### Migrations
- ❌ Running `alembic revision --autogenerate` without first reviewing the diff
- ❌ Creating migrations with non-idempotent index creation (missing `if_not_exists=True`)
- ❌ Committing a migration with an empty or trivially incorrect `downgrade()`

---

## Environment Variables Quick Reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `JWT_SECRET_KEY` | ✅ | HS256 signing secret |
| `CLOUD_STORAGE_PROVIDER` | ✅ | `gcp` or `aws` |
| `CLOUD_STORAGE_BUCKETNAME` | ✅ | Target bucket name |
| `CLOUD_STORAGE_SECRET` | ✅ | GCP SA JSON or AWS secret key |
| `CLOUD_STORAGE_ACCOUNTNAME` | ✅ | GCP SA email or AWS access key ID |
| `GEMINI_API_KEY_1` | ✅ | Primary Gemini API key |
| `CELERY_BROKER_URL` | ✅ | RabbitMQ AMQP URL |
| `ENTITY_MGMT_BASE_URL` | ✅ | External entity service URL |
| `IS_NOTIFICATION_ENABLED` | opt | Enable email (default: true) |
| `DEFAULT_TENANT_CODE` | opt | Seed data scope (default: "default") |
| `CLOUD_STORAGE_REGION` | opt (AWS) | AWS region |
