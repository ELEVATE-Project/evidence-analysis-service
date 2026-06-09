# Skill: Cloud Storage Operations

How to use `StorageService` correctly in service code. This is the API reference for developers writing code that reads or writes files.

For provider-specific behavior (GCP vs AWS), IAM permission requirements, signed URL troubleshooting, and bootstrap diagnosis — see the `storage-expert` agent.

## Import

```python
from services.storage_service import (
    StorageService,
    StorageError,
    StorageUploadError,
    StorageDownloadError,
    StoragePermissionError,
)

storage = StorageService()  # validates provider + bucket at init
```

**Critical**: All `StorageService` methods are `async`. Always `await` them. Forgetting `await` returns a coroutine object, not bytes — this is one of the most common bugs.

## StorageService API

### upload_file

```python
stored_path = await storage.upload_file(
    file_content=bytes_data,              # bytes
    file_path="projects/sample.csv",      # relative or absolute OK
    content_type="text/csv",
)
# Returns: "/projects/sample.csv" (normalized absolute path)
# Store this returned path in the DB — do NOT store the path you passed in
```

### download_file

```python
content: Optional[bytes] = await storage.download_file("/user_id/exec_id/output.csv")
# Returns None if object does not exist — does NOT raise for 404
# Raises StoragePermissionError for access denied
# Raises StorageDownloadError for other failures
```

### get_file_path (for subprocess use)

```python
local_path: str = await storage.get_file_path("/user_id/exec_id/input.csv")
# Downloads to a unique temp file: /tmp/evidence_analysis/{uuid}.csv
# UUID-prefixed — concurrent calls for same object are safe
# Caller MUST clean up the temp file after subprocess finishes
# Not suitable for large files in API request path (download + write + read = 3x memory)
```

### generate_upload_url (signed PUT for frontend)

```python
result = await storage.generate_upload_url(
    file_path="/user_id/exec_id/input.csv",
    content_type="text/csv",
    expiration=900,       # seconds; upload URLs expire in 900s (settings.UPLOAD_URL_EXPIRY)
)
# Returns: {"url": "...", "method": "PUT", "headers": {}, "expires_in_seconds": 900}
# Frontend does: fetch(result["url"], { method: "PUT", body: fileArrayBuffer })
# Content-Type NOT bound in signed URL — intentional to avoid 403 from browser variation
```

### generate_download_url (signed GET)

```python
result = await storage.generate_download_url(
    file_path="/user_id/exec_id/output.csv",
    expiration=600,                          # download URLs expire in 600s
    response_filename="analysis_report.csv", # optional: sets Content-Disposition header
)
# Returns: {"url": "...", "method": "GET", "headers": {}, "expires_in_seconds": 600}
```

### get_file_metadata

```python
meta: Optional[dict] = await storage.get_file_metadata("/path/to/file.csv")
# Returns: {"size_bytes": 12345, "content_type": "text/csv"} or None if not found
# Use to verify a file exists and get its size after upload completion
```

### delete_file

```python
await storage.delete_file("/path/to/file.csv")
# Idempotent: no error if the object does not exist
```

### build_execution_file_path

```python
path = storage.build_execution_file_path(
    user_id=current_user.id,
    execution_id=str(execution.id),
    file_name="evidence_input.csv",    # user-provided name; will be sanitized
)
# Returns: "/safe_user_id/safe_exec_id/evidence_input.csv"
# All path segments sanitized: [^A-Za-z0-9._-] → "_"
# ALWAYS use this for execution files — never construct the path manually
```

## Error Handling Pattern

```python
try:
    content = await storage.download_file(file_path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found in storage")
except StoragePermissionError as exc:
    logger.error("storage_access_denied  path=%s  error=%s", file_path, exc)
    raise HTTPException(status_code=500, detail="Storage access denied") from exc
except StorageDownloadError as exc:
    logger.error("storage_download_failed  path=%s  error=%s", file_path, exc)
    raise HTTPException(status_code=500, detail="Storage download failed") from exc
```

Note: `download_file()` returns `None` for 404 — it does NOT raise. Check for `None` explicitly.

## File Path Rules

```python
# Paths stored in DB: always absolute, leading slash, no bucket prefix
"/user_id/exec_id/evidence_input.csv"   ✓ store this
"gs://my-bucket/user_id/exec_id/file"   ✗ never store (legacy; handled by _normalize_absolute_file_path)
"s3://my-bucket/user_id/exec_id/file"   ✗ never store

# Path traversal: _normalize_absolute_file_path() raises ValueError on ".."
# Object key construction: always via build_execution_file_path() for execution files
```

## Async Usage — Critical Rules

```python
# ✓ In async service method: always await
async def upload_result(self, exec_id: str, data: bytes) -> str:
    path = storage.build_execution_file_path(self.user_id, exec_id, "output.csv")
    return await storage.upload_file(data, path, "text/csv")

# ✓ In sync function running in a thread (e.g., execution_processor.py):
def download_in_thread(file_path: str) -> Optional[bytes]:
    return asyncio.run(storage.download_file(file_path))  # OK — no running event loop in thread

# ❌ Wrong: missing await — returns coroutine, not bytes
content = storage.download_file(path)

# ❌ Wrong: asyncio.run() inside a running event loop (async def context)
async def bad_example():
    content = asyncio.run(storage.download_file(path))  # RuntimeError: loop already running
```

## Bootstrap and Sample CSV Re-upload

Sample CSVs are uploaded during startup by `services/bootstrap.py`. If they're missing:

```bash
python scripts/upload_sample_csvs.py
```

Bootstrap also runs `run_deep_validation()` on every startup: write probe → read → sign URL → delete. If this fails, the app won't start — check cloud credentials and IAM.

## Anti-patterns

❌ `gs_client.bucket(name).blob(key).upload_from_string(...)` directly in service code — always use `StorageService`
❌ `Path("/tmp/file.csv").write_bytes(content)` for persistent storage — cloud-only
❌ `f"gs://{bucket}/{key}"` or `f"s3://{bucket}/{key}"` — never construct cloud URLs manually
❌ `os.environ["CLOUD_STORAGE_SECRET"]` in service code — use `settings` from `core/config.py`
❌ `storage.download_file(path)` without `await` in async context — returns coroutine
❌ Storing the OS temp path (`/tmp/evidence_analysis/...`) in the database — store only the cloud object path
❌ Not checking `if content is None` after `download_file()` — it silently returns None for 404
