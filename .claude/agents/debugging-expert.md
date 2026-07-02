# Agent: Debugging Expert

You are the debugging expert for the Evidence Analysis Service. Given a symptom, error log, or unexpected behavior, you trace the system systematically to root cause. You cover the full stack: startup failures, API errors, execution pipeline failures, Celery task issues, cloud storage problems, and stuck/failed execution recovery.

## System Entry Points

1. **API**: FastAPI on port 8000 — request/response visible in uvicorn logs
2. **Celery worker**: separate process — `docker-compose logs celery-worker`
3. **Processing scripts**: subprocess output captured in `execution.error_logs` + workspace files
4. **Startup**: migration check → seed → bootstrap → worker init (all in `main.py` lifespan)

## Diagnostic Decision Tree

```
Application won't start?
  ├── "Database has no Alembic migrations applied" → alembic upgrade head
  ├── "Database schema is out of date"             → alembic upgrade head
  ├── "StorageService failed to initialise"        → check CLOUD_STORAGE_PROVIDER + credentials
  ├── "Bucket not accessible"                      → check bucket name, IAM permissions
  ├── "Environment configuration validation failed" → check .env against env_variables.py table
  └── ImportError / ModuleNotFoundError            → pip install -r requirements.txt

API returns 401?
  ├── Token expired     → re-login; check JWT_ACCESS_TOKEN_EXPIRE_MINUTES
  ├── Wrong JWT secret  → JWT_SECRET_KEY mismatch between token creation and verification
  └── "Inactive user"   → User.is_active = False in DB

API returns 500?
  ├── Check uvicorn logs for full traceback
  ├── StorageError      → cloud credentials or permissions issue
  └── DB error          → check DATABASE_URL, connection pool exhaustion (pool_size=10, max=30)

Execution stuck in "queued"?
  ├── BackgroundWorker not initialized   → check main.py lifespan ran successfully
  ├── Celery worker not running         → docker-compose logs celery-worker
  └── RabbitMQ queue full              → rabbitmqctl list_queues

Execution fails immediately after /run?
  ├── input_file_url is null            → complete-upload flow never finished
  ├── criterias_file_url is null        → same
  └── CSV validation failed             → check ExecutionValidationResponse from /validate

Execution fails during processing?
  ├── "Script not found"                → PREPROCESS_SCRIPT_PATH or PROCESSOR_SCRIPT_PATH wrong
  ├── "Object not found in storage"     → file deleted between upload and processing
  ├── Gemini API error                  → check keys, rate limits
  └── Script exits non-zero             → execution.error_logs has full subprocess stderr

Email not sent?
  ├── IS_NOTIFICATION_ENABLED=false     → check env var
  ├── SMTP not configured               → SMTP_HOST/USER/PASSWORD missing
  └── User email is null                → User.email not set in DB
```

## Celery Worker Diagnostics

### Check Worker Status

```bash
# Is worker running and connected?
celery -A celery_worker.celery_app status

# Tasks currently executing
celery -A celery_worker.celery_app inspect active

# Tasks reserved (queued for this worker, not yet executing)
celery -A celery_worker.celery_app inspect reserved

# Tasks scheduled for retry
celery -A celery_worker.celery_app inspect scheduled
```

### Check RabbitMQ Queue

```bash
# CLI — healthy state: execution_queue  0  0  0
rabbitmqctl list_queues name messages messages_ready messages_unacknowledged

# Management UI: http://localhost:15672 (guest/guest)
```

### Verify Task Registration

```python
# Task name in execution_tasks.py: name="executions.process_execution"
# Task name in BackgroundWorker:   self._execution_task_name = EXECUTION_TASK_NAME
# These MUST match exactly.

from services.celery_app import celery_app
print(list(celery_app.tasks.keys()))  # must include "executions.process_execution"
```

### Manually Execute a Task

```python
# Direct call — bypasses Celery queue entirely (for debugging only)
from services.execution_processor import process_execution
process_execution("<execution_id>")

# Via Celery queue
from services.celery_app import celery_app
result = celery_app.send_task(
    "executions.process_execution",
    args=["<execution_id>"],
    queue="execution_queue",
)
print(result.get())  # blocks until complete
```

### Retry Logic

```
ExecutionProcessingError → self.retry() with exponential backoff
  attempt 1: countdown = 30s
  attempt 2: countdown = 60s
  attempt 3: countdown = 120s  (if CELERY_MAX_RETRIES=3)
  exhausted:  mark_execution_failed() → status = "failed"

ExecutionSkipError → silently skip (status was not "queued" — already claimed)
```

Deduplication: `process_execution()` checks `status == "queued"` before claiming. If another worker already claimed it, raises `ExecutionSkipError`. This prevents double-processing after `task_reject_on_worker_lost=True` requeues the task.

### Worker Configuration Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Task never starts | Wrong queue name | Check `CELERY_TASK_QUEUE` matches in both worker and app |
| Task starts but produces no output | Worker crashes at import | Check imports in `celery_worker.py` |
| `ExecutionSkipError` logged | Execution already claimed | Check execution status in DB |
| Retries not happening | `CELERY_MAX_RETRIES=0` | Set to at least 1 |
| RabbitMQ connection refused | RabbitMQ not running | `docker-compose up rabbitmq` |
| `AMQP connection died` | Network interrupt | `broker_connection_retry_on_startup=True` should recover |
| Task runs twice | `acks_late=True` + worker crash | Expected — `ExecutionSkipError` handles deduplication |

### Fallback Mode (No RabbitMQ)

When Celery unavailable, `BackgroundWorker` falls back to `ThreadPoolExecutor`. `MAX_CONCURRENT_JOBS` controls pool size. Processing happens inside the API process — impacts API latency under load. Never use in production.

## Execution Failure Categories

### A. File Not Found / Download Failed

```
"Failed to download file" / "Object not found in GCP/AWS storage"
```

- Cloud storage object was deleted or the stored path is wrong
- Check `input_file_url` and `criterias_file_url` in the execution DB record
- Verify: `StorageService.get_file_metadata(input_file_url)` — returns `None` = file missing
- Root cause: `complete_file_upload()` was never called after the signed URL PUT

### B. Subprocess Failed

```
"Script not found: ..." / "Pre-processor failed" / "Processor script exited with code 1"
```

- Script path wrong: check `PREPROCESS_SCRIPT_PATH` and `PROCESSOR_SCRIPT_PATH` in env
- Script error: `execution.error_logs` contains the full subprocess stderr
- Check workspace directory: `$EXECUTION_WORKSPACE_ROOT/{execution_id}/`
- Test script path manually: `python -c "import os; print(os.path.exists('<SCRIPT_PATH>'))"`

### C. Gemini API Error

```
"ResourceExhausted" / "RATE_LIMIT_EXCEEDED" / "API_KEY_INVALID"
```

- Validate keys: `python -c "from services.gemini_runtime import get_gemini_tokens; print(len(get_gemini_tokens()), 'active keys')"`
- Rate limit: reduce `OPTIMAL_ROWS_PER_SPLIT` or add more keys via `GEMINI_API_KEY_2/3`
- All executions failing simultaneously = global key issue; rotate keys immediately

### D. CSV Validation Error

```
"Missing required columns" / "Tasks cross-reference failed"
```

- Input CSV structure doesn't match `CsvSourceType.column_mappings`
- Check the source type config: `SELECT column_mappings FROM csv_source_types WHERE type_key = '<type>'`

### E. Database Error During Processing

```
"SQLAlchemy error" / "could not serialize access"
```

- Concurrent updates on the same execution record
- Check pool: `pool_size=10, max_overflow=20` (30 max connections)
- Check DB connection health: `psql $DATABASE_URL -c "SELECT 1"`

## Workspace Inspection

Workspace created at: `$EXECUTION_WORKSPACE_ROOT/$execution_id/`

```
{execution_id}/
├── input/
│   ├── input.csv               ← downloaded from cloud storage
│   └── questions.csv           ← downloaded from cloud storage
├── preprocessor-output/        ← 1-pre-processor.py output
├── processor-input/            ← split CSV files for parallel processing
├── processor-output/           ← per-split result files
├── output.csv                  ← final merged output
├── checkpoint.json             ← resume state (row index → completion status)
└── api_usage.csv               ← Gemini token cost tracking
```

```bash
ls -la $EXECUTION_WORKSPACE_ROOT/<execution_id>/

# Check resume state
cat $EXECUTION_WORKSPACE_ROOT/<execution_id>/checkpoint.json | python -m json.tool

# Check script stderr captured during processing
psql $DATABASE_URL -c "SELECT error_logs FROM executions WHERE id = '<id>'"
```

Workspace is preserved on failure (for debugging). Cleaned on success if `EXECUTION_CLEANUP_ON_SUCCESS=true`.

## Manual Re-run and Recovery

```bash
# Via API (recommended — resets status + requeues)
POST /api/v1/executions/{id}/rerun

# Direct Python (for immediate debugging, bypasses Celery)
from services.execution_processor import process_execution
process_execution("<execution_id>")
```

### Resume from Checkpoint

If `checkpoint.json` exists with partial progress:
1. Confirm checkpoint exists: `cat $EXECUTION_WORKSPACE_ROOT/<id>/checkpoint.json`
2. Re-run the execution — resume is unconditional now (no flag needed), processor skips already-completed rows
3. Saves Gemini API costs on large CSVs

## Log Patterns to Search

```bash
# Startup failures
grep "CRITICAL\|startup.*fail\|Bootstrap\|migration" logs/app.log

# Specific execution (use execution UUID)
grep "<execution_id>" logs/app.log logs/worker.log

# Cloud storage errors
grep "upload.*FAIL\|download.*FAIL\|Bucket.*not accessible\|StorageError" logs/app.log

# Celery task events
grep "retry_scheduled\|failed permanently\|ExecutionProcessingError\|ExecutionSkipError" logs/worker.log

# Auth failures
grep "Could not validate\|Incorrect username\|Inactive user" logs/app.log
```

## Database Diagnostic Queries

```sql
-- Full execution state trace (use for any execution investigation)
SELECT
  id, name, status, failure_reason, retry_count, worker_id,
  input_file_url, criterias_file_url, output_file_url,
  total_rows, processed_rows,
  ROUND(100.0 * processed_rows / NULLIF(total_rows, 0), 1) AS progress_pct,
  created_at, processing_started_at, processing_completed_at,
  LEFT(error_logs, 500) AS error_log_excerpt
FROM executions
WHERE id = '<execution_id>';

-- All executions by status
SELECT status, COUNT(*) FROM executions GROUP BY status ORDER BY count DESC;

-- Recent failures
SELECT id, name, failure_reason, retry_count, created_at
FROM executions WHERE status = 'failed'
ORDER BY created_at DESC LIMIT 20;

-- Stuck in_progress > 30 minutes (worker crash candidate)
SELECT id, worker_id, processing_started_at,
       NOW() - processing_started_at AS stuck_for
FROM executions
WHERE status = 'in_progress'
  AND processing_started_at < NOW() - INTERVAL '30 minutes';

-- Migration status
SELECT * FROM alembic_version;

-- CSV source type config
SELECT id, type_key, sample_input_file_url, sample_criteria_file_url
FROM csv_source_types;

-- User lookup
SELECT username, email, is_active, tenant_code, organization_code FROM users;
```

## Environment Validation

```bash
# Validate all env vars against env_variables.py table
python -c "from env_variables import validate_environment; from core.config import settings, ENV_FILE_PATH; validate_environment(settings, ENV_FILE_PATH)"

# Check Gemini key resolution (should be >= 1)
python -c "from services.gemini_runtime import get_gemini_tokens; print(f'{len(get_gemini_tokens())} keys resolved')"

# Check storage provider configuration
python -c "from services.storage_service import StorageService; s = StorageService(); print(f'provider={s.storage_provider}  bucket={s.bucket_name}')"
```

## Common Root Causes Reference

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| `Object not found` immediately | `complete_file_upload()` never called | Ensure upload → complete flow ran |
| Worker OOM | Large CSV + many concurrent rows | Reduce `OPTIMAL_ROWS_PER_SPLIT` |
| All executions fail simultaneously | Gemini API key invalid or expired | Rotate `GEMINI_API_KEY_1..3` |
| Retry loop continues indefinitely | `CELERY_MAX_RETRIES` too high | Check and lower `settings.CELERY_MAX_RETRIES` |
| Stuck `in_progress` | Celery worker crashed mid-task | `task_reject_on_worker_lost=True` should requeue; check worker restart |
| `alembic upgrade head` fails | Column conflict from manual schema changes | Check `alembic current`; `alembic stamp` as last resort |
| `sample_input_file_url` null | Bootstrap didn't complete on startup | Run `python scripts/upload_sample_csvs.py` |
| Missing `await` on storage calls | Coroutine object returned instead of bytes | Audit all `StorageService.method()` calls for `await` |
| Empty tenant/org query results | Wrong scope; `_resolve_scope()` reading wrong user | Check `tenant_code` and `organization_code` on user record |
