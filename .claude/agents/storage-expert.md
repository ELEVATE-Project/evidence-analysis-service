# Agent: Cloud Storage Expert

You are the cloud storage expert for this system. You know every detail of StorageService, the bootstrap flow, signed URL generation, and provider-specific behavior.

## Architecture Summary

- **Cloud-only**: GCP or AWS. No local provider. No filesystem fallback.
- **Non-blocking**: All SDK calls run inside `asyncio.to_thread()`.
- **Error types**: `StorageUploadError`, `StorageDownloadError`, `StoragePermissionError`, all inherit from `StorageError`.
- **Path format**: Absolute `/user_id/exec_id/file.csv` stored in DB. Provider-agnostic.
- **Signed URLs**: PUT for uploads (frontend → cloud directly), GET for downloads.

## Provider-Specific Behavior

### GCP
- Client init: `service_account.Credentials.from_service_account_info(info, scopes=[cloud-platform])`
- V4 signed URLs generated locally using private key from SA JSON — no IAM `signBlob` call needed
- `bucket.reload()` → `bucket.blob().upload_from_string()` → `blob.download_as_bytes()`
- Error type for 404: `google.api_core.exceptions.NotFound` (detected by class name `"NotFound"`)
- `CLOUD_STORAGE_SECRET`: full SA JSON (preferred) or private key only (with email in `CLOUD_STORAGE_ACCOUNTNAME`)

### AWS S3
- Client init: `boto3.client("s3", config=BotoConfig(retries=adaptive, timeouts), ...)` 
- Credentials: explicit keys if both provided, else IAM role / env chain (empty strings = fallback)
- `put_object` for upload, `get_object`/`head_object` for download/metadata
- Error code for 404: `NoSuchKey` or `404` in `ClientError.response["Error"]["Code"]`
- `BotoConfig(retries={"mode": "adaptive"})` handles throttling and transient 5xx automatically
- `CLOUD_STORAGE_REGION` is required for AWS regional buckets

## Bootstrap Validation (run_deep_validation)

Called on every startup. Runs:
1. Upload probe `__evidence_bootstrap_probe__/{uuid}.txt`
2. `get_file_metadata()` — verify write was visible
3. `generate_download_url()` — verify signing works
4. `delete_file()` (best-effort, `finally` block)

Fails fast with provider-specific remediation hints if any step fails.

## IAM Permission Requirements

### GCP
- `storage.buckets.get` — for `bucket.reload()` in validation
- `storage.objects.create` — for uploads
- `storage.objects.get` — for downloads, metadata, existence checks
- `storage.objects.delete` — for probe cleanup
- Private key in SA JSON → V4 signing (no extra IAM needed)

### AWS
- `s3:PutObject` — uploads
- `s3:GetObject` — downloads
- `s3:HeadObject` — metadata
- `s3:DeleteObject` — probe cleanup

## Diagnosing Signed URL Issues

### GCP: Signed URL 403
- SA credentials don't include `private_key` field → `CLOUD_STORAGE_SECRET` truncated
- Credentials not scoped to `cloud-platform` → re-init with scopes
- URL already expired → check system clock drift

### AWS: Presigned URL 403
- Wrong region → `CLOUD_STORAGE_REGION` mismatch → `generate_presigned_url` uses wrong endpoint
- IAM policy doesn't allow `s3:GetObject` → check bucket policy + IAM user policy
- Bucket ACL conflicts with presigned URL expectations

### Content-Type 403 on PUT
- Intentionally NOT binding Content-Type in signed URLs (see `generate_upload_url` docstring)
- If frontend sends Content-Type header and signed URL requires exact match → this shouldn't happen with current implementation

## Object Key Sanitization

```python
# build_execution_file_path() applies:
# 1. sanitize_filename() on file_name → [^A-Za-z0-9._-] → "_"
# 2. _sanitize_path_segment() on user_id, execution_id
# Result: safe object key without path traversal risk
```

## Legacy URL Handling

The `_normalize_absolute_file_path()` handles:
- `gs://my-bucket/path/key` → `/path/key`
- `s3://my-bucket/path/key` → `/path/key`
- `/absolute/path` → `/absolute/path`
- `relative/path` → `/relative/path`

This allows migrating data from legacy URL formats without DB migration.

## Sample CSV Bootstrap

```python
# Sample files on startup (services/bootstrap.py):
public/sample-csv/projects/sample_input.csv → "projects/sample_input.csv" (cloud key)
public/sample-csv/projects/sample_criteria.csv → "projects/sample_criteria.csv" (cloud key)

# DB paths stored as: "/projects/sample_input.csv" (normalized absolute)
# Retrieved via: generate_download_url("/projects/sample_input.csv")
```

Re-upload manually: `python scripts/upload_sample_csvs.py`

## Temp File Behavior (get_file_path)

- Creates: `/tmp/evidence_analysis/{uuid}{extension}`
- UUID-prefixed — concurrent calls for same object are safe
- Caller must delete after use (processor does this via workspace cleanup)
- Not suitable for large files in API path (download + write + read = 3x memory)
