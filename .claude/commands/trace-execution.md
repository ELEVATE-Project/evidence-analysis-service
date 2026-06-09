# Command: Trace Execution Flow

**Usage:** `/trace-execution <execution_id>`

Trace the complete lifecycle of an execution from creation to completion or failure.

## What This Command Does

Given an execution ID, trace:
1. API call sequence that created/ran it
2. File upload state
3. Celery task dispatch
4. Processing pipeline state
5. Output file location
6. Email notification status

## Trace Script

```sql
-- Complete execution state
SELECT
  id,
  name,
  status,
  csv_type_id,
  tenant_code,
  organization_code,
  input_file_url,
  input_file_size,
  criterias_file_url,
  criterias_file_size,
  output_file_url,
  output_file_size,
  total_rows,
  processed_rows,
  ROUND(100.0 * processed_rows / NULLIF(total_rows, 0), 1) AS progress_pct,
  retry_count,
  worker_id,
  failure_reason,
  error_logs,
  created_at,
  processing_started_at,
  processing_completed_at,
  completed_at,
  notification_sent,
  notification_sent_at
FROM executions
WHERE id = '<execution_id>';
```

## State Interpretation

| status | input_file_url | processing_started_at | Meaning |
|--------|---------------|----------------------|---------|
| queued | NULL | NULL | Created but no files uploaded |
| queued | SET | NULL | Files uploaded, not yet started |
| in_progress | SET | SET | Processor running |
| in_progress | SET | SET (>30m ago) | Likely stuck — worker died |
| completed | SET | SET | Done — check output_file_url |
| failed | SET | SET | Failed — read failure_reason + error_logs |

## Pipeline Steps to Verify

```python
# Step 1: Draft created?
GET /api/v1/executions/<id>
# → status = "queued", input_file_url = null

# Step 2: Input file uploaded?
# → input_file_url set, input_file_size > 0

# Step 3: Criteria file uploaded?
# → criterias_file_url set, criterias_file_size > 0

# Step 4: Validation passed?
POST /api/v1/executions/<id>/validate
# → validation_result.is_valid = true

# Step 5: Run triggered?
POST /api/v1/executions/<id>/run
# → status changes from "queued" to "in_progress"

# Step 6: Processing complete?
# → status = "completed", output_file_url set, total_rows = processed_rows

# Step 7: Report available?
GET /api/v1/reports/<id>
```

## Check Workspace

```bash
ls -la $EXECUTION_WORKSPACE_ROOT/<execution_id>/
cat $EXECUTION_WORKSPACE_ROOT/<execution_id>/checkpoint.json | python -m json.tool
```

## Check Celery Task

```bash
# If you have the Celery task ID (logged when submitted):
celery -A celery_worker.celery_app result <task_id>

# Or look for the execution in worker logs:
docker-compose logs celery-worker 2>&1 | grep <execution_id>
```

## Verify Cloud Storage

```python
from services.storage_service import StorageService
import asyncio

storage = StorageService()

async def check():
    # Check input file
    meta = await storage.get_file_metadata("/user_id/exec_id/input.csv")
    print(f"Input file: {meta}")

    # Check output file
    meta = await storage.get_file_metadata("/user_id/exec_id/output.csv")
    print(f"Output file: {meta}")

asyncio.run(check())
```
