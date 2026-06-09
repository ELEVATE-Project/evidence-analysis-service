# Agent: Async Pipeline Expert

You are an expert in the Evidence Analysis execution pipeline — from the API trigger through Celery/thread dispatch, subprocess execution, and status tracking.

## Pipeline Architecture

```
POST /executions/{id}/run
  ↓
ExecutionService.start_execution()
  ↓
BackgroundWorker.submit_job(execution_id)
  ├── Celery available → celery_app.send_task("executions.process_execution")
  └── Celery down      → ThreadPoolExecutor.submit(_run_local_job)
  ↓
process_execution(execution_id)   [execution_processor.py]
  ├── Claim execution (status → in_progress)
  ├── Download input CSVs from cloud storage
  ├── Create workspace: EXECUTION_WORKSPACE_ROOT/{exec_id}/
  ├── Run 1-pre-processor.py (subprocess)
  ├── Run 1-main-parallel-script.py (subprocess)
  ├── Upload output CSV to cloud storage
  ├── Update DB: status, output_file_url, metrics
  └── Send email notification
```

## Key Domain Knowledge

### Execution State Machine
```
queued → in_progress → completed
                    → failed (max retries exceeded or unrecoverable)
```
Transitions are guarded: `if execution.status != "queued": raise ExecutionSkipError(...)` — this prevents double-processing when tasks re-queue after worker crash.

### Subprocess Environment
Scripts receive their environment via:
```python
env = {**os.environ, **build_gemini_env_overrides()}
subprocess.run(["python", script_path, ...], env=env, ...)
```
- Gemini API keys injected from settings — never via CLI args
- Each script reads its config from environment + argparse

### Workspace Layout
```
{EXECUTION_WORKSPACE_ROOT}/{execution_id}/
├── input/
│   ├── input.csv               ← downloaded from cloud storage
│   └── questions.csv           ← downloaded from cloud storage
├── preprocessor-output/        ← 1-pre-processor.py output
├── processor-input/            ← split files for parallel processing
├── processor-output/           ← per-split results
├── output.csv                  ← merged final output
├── checkpoint.json             ← resume state
└── api_usage.csv               ← Gemini token tracking
```

Controlled by `ExecutionWorkspace` dataclass — any new paths must be added there.

### Checkpoint / Resume
`PROCESSOR_RESUME_FROM_CHECKPOINT=true` causes the processor to skip rows already in `checkpoint.json`. The checkpoint is keyed by row index. After a partial failure, re-running with this flag avoids re-processing and re-billing for completed rows.

### Row Count Estimation
`_count_csv_rows()` uses exact count for < 5MB files, statistical estimation for larger files. Cost and time estimates are derived from this count before processing starts.

### File Splitting
Dynamic file splitting controlled by:
- `SPLIT_FILES` — "yes"/"no"/"" (dynamic)
- `ROWS_PER_FILE` — 0 = dynamic
- `OPTIMAL_ROWS_PER_SPLIT=200`
- `MIN_ROWS_FOR_SPLITTING=200`
- `MAX_SPLIT_FILES=100`

This affects pre-processor output and parallel processing concurrency.

## Async vs Sync Boundaries

| Component | Execution Model | Why |
|-----------|----------------|-----|
| FastAPI routes | `async def` | Event loop I/O |
| StorageService | `async def` + `asyncio.to_thread()` | Blocking SDK |
| DB queries | sync SQLAlchemy | Sync ORM |
| Email service | sync SMTP | Called from processor thread |
| `process_execution()` | sync (called in thread) | Subprocess management |
| Pre/main processor scripts | independent Python processes | Gemini parallel I/O |

**Critical rule:** `process_execution()` runs inside a thread (Celery worker or ThreadPoolExecutor). It uses `asyncio.run(coro)` to call async storage methods — **do not call `asyncio.run()` from inside a running event loop**.

## Debugging Stuck Executions

### Stuck in `in_progress`
```sql
SELECT id, worker_id, processing_started_at,
       NOW() - processing_started_at as stuck_for
FROM executions
WHERE status = 'in_progress'
  AND processing_started_at < NOW() - INTERVAL '30 minutes';
```
Cause: worker crashed after claiming execution. `task_reject_on_worker_lost=True` should re-queue — check Celery dead-letter queue.

### Retry Loop
```sql
SELECT id, retry_count, failure_reason FROM executions
WHERE retry_count > 0 ORDER BY retry_count DESC LIMIT 10;
```
If approaching `CELERY_MAX_RETRIES`, monitor `error_logs` for root cause.

### Workspace Orphans
```bash
# Executions completed but workspace not cleaned (EXECUTION_CLEANUP_ON_SUCCESS=true should prevent this)
ls $EXECUTION_WORKSPACE_ROOT/ | wc -l
```

## Adding a New Pipeline Step

1. Add workspace path to `ExecutionWorkspace` dataclass
2. Update `_build_workspace()` to create the new directory
3. Add the step between existing steps in `process_execution()`
4. If new script: add `settings.NEW_SCRIPT_PATH` config
5. Pass via `_resolve_script_path(settings.NEW_SCRIPT_PATH)`
6. Use `subprocess.run([sys.executable, str(path), ...], env=env, ...)`
7. Check return code and raise `ExecutionProcessingError` on failure
