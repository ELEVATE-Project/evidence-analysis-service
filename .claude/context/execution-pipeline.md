# Execution Pipeline Context

## Overview

The execution pipeline processes CSV evidence data through Google Gemini AI. Each execution is an isolated job with its own workspace, file downloads, subprocess invocations, and output upload.

## API Endpoints (in order of use)

```
POST   /api/v1/executions/                          Create draft
POST   /api/v1/executions/{id}/files/{type}/upload-url  Get signed PUT URL
POST   /api/v1/executions/{id}/files/{type}/complete    Mark file uploaded
POST   /api/v1/executions/{id}/validate             Validate CSV structure
POST   /api/v1/executions/{id}/run                  Queue for processing
GET    /api/v1/executions/{id}                      Poll status
GET    /api/v1/reports/{id}                         Get report data
GET    /api/v1/reports/{id}/download                Get signed download URL
POST   /api/v1/notifications/executions/{id}/email  Send completion email
POST   /api/v1/executions/{id}/rerun               Re-queue failed/completed
```

File types: `"input"` (evidence CSV) and `"questions"` (criteria CSV)

## Processing Script Architecture

### Pre-processor (`scripts/pre-processor/1-pre-processor.py`)
- Merges input CSV with questions CSV
- Applies school filtering (optional)
- Splits output into chunks for parallel processing
- Config via args + env vars
- Output: multiple split CSV files in `preprocessor-output/`

### Main Processor (`scripts/processor/1-main-parallel-script.py`)
- Reads split CSV files from `processor-input/`
- Calls Gemini API for each evidence row
- Supports image URLs, PDFs, Excel files as evidence
- Writes per-split result CSVs to `processor-output/`
- Merges into `output.csv`
- Writes `checkpoint.json` for resume support
- Writes `api_usage.csv` for cost tracking

### Gemini Multi-Key Rotation
- Up to 3 API keys: `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`
- Resolved by `get_gemini_tokens()` in `services/gemini_runtime.py`
- Injected into subprocess via `build_gemini_env_overrides()`
- Model: `GEMINI_MODEL=gemini-2.5-flash`

## Celery Task Configuration

```python
# execution_tasks.py
@celery_app.task(
    bind=True,
    name="executions.process_execution",
    acks_late=True,              # ack after completion, not on receipt
    reject_on_worker_lost=True,  # requeue on worker crash
)
```

**Retry logic:**
```
ExecutionProcessingError → self.retry(countdown=30*(2^retry_num))
  → retries 1/3: 30s cooldown
  → retries 2/3: 60s cooldown
  → retries 3/3: 120s cooldown (if CELERY_MAX_RETRIES=3)
  → exhausted: mark_execution_failed()
ExecutionSkipError → skip (status not queued)
```

**Deduplication:** `process_execution()` checks `status == "queued"` before claiming. If status changed (e.g. concurrent worker), raises `ExecutionSkipError`.

## File Split Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `SPLIT_FILES` | "" (dynamic) | "yes"/"no"/"" |
| `ROWS_PER_FILE` | 0 (dynamic) | manual split size |
| `ENABLE_DYNAMIC_SPLITTING` | true | master switch |
| `MIN_ROWS_FOR_SPLITTING` | 200 | min rows to trigger split |
| `OPTIMAL_ROWS_PER_SPLIT` | 200 | target rows per split |
| `MAX_SPLIT_FILES` | 100 | hard cap on splits |

## Workspace Lifecycle

```
Created: _build_workspace() in execution_processor.py
Exists at: $EXECUTION_WORKSPACE_ROOT/$execution_id/
Cleaned: EXECUTION_CLEANUP_ON_SUCCESS=true (default) removes after success
Preserved on failure: for debugging (manual cleanup needed)
```

## Cost Estimation

```python
estimated_cost = total_rows * ESTIMATED_COST_PER_INPUT_ROW  # default: $0.001/row
estimated_time = total_rows * ESTIMATED_TIME_SECONDS_PER_INPUT_ROW  # default: 0.5s/row
```
Actual cost tracked per row in `api_usage.csv` via `actual_cost` column.

## Checkpoint / Resume

```json
// checkpoint.json structure
{
  "processed_rows": 450,
  "total_rows": 1000,
  "files": {
    "input": {"status": "downloaded"},
    "questions": {"status": "downloaded"},
    "output": {"last_row": 450}
  }
}
```

Resume is unconditional — the processor always picks up from `processed_rows` if a checkpoint exists; there is no flag to disable it. Just re-run the execution. The workspace is never wiped before a run starts (only after a successful one), so a failed run's checkpoint and partial output survive for the next attempt.

## Status Transitions

```
queued         Initial state — files not yet uploaded
↓ files uploaded
queued         Ready to process (files set in DB)
↓ POST /run
in_progress    Processing started (processing_started_at set)
↓
completed      output_file_url set, all rows processed
failed         failure_reason + error_logs set
```

`rerun` endpoint resets failed/completed execution back to `queued` and re-queues.
