# Skill: Security Review

Review new code or PR changes for security issues specific to this repository.

## Authentication & Authorization

### JWT Checks
- [ ] All protected endpoints have `current_user: UserResponse = Depends(AuthService.get_current_user)`
- [ ] `oauth2_scheme` uses `tokenUrl="/api/v1/auth/login"` (correct)
- [ ] JWT `exp` claim is verified by `jwt.decode()` (python-jose does this automatically)
- [ ] `JWT_SECRET_KEY` is never logged or included in responses
- [ ] Token creation uses `datetime.now(timezone.utc)` — never naive datetime

### Authorization Gaps
- [ ] Executions: `created_by == user_id` check before any mutation
- [ ] Reports: only for completed executions owned by the user
- [ ] Download URLs: `_validate_downloadable_file_path()` enforces path scope
- [ ] Admin-only operations (`is_superuser`) are explicitly checked

## Multi-tenancy Isolation

```python
# REQUIRED pattern for every data query:
db.query(Execution).filter(
    Execution.tenant_code == tenant_code,
    Execution.organization_code == organization_code,
    Execution.created_by == user_id,   # user-level isolation
)
```
- [ ] No query returns data without `tenant_code + organization_code` filter
- [ ] Cross-tenant reads are impossible (verify at service layer, not just router)

## Input Validation

- [ ] File upload: content type checked against `_ALLOWED_CSV_CONTENT_TYPES`
- [ ] File size: checked against `settings.MAX_UPLOAD_SIZE` (100MB)
- [ ] File extension: checked against `settings.ALLOWED_EXTENSIONS` (`.csv` only)
- [ ] Filename sanitization: `sanitize_filename()` applied before object key construction
- [ ] Path traversal: `_normalize_absolute_file_path()` raises `ValueError` on `..`
- [ ] `_DOWNLOADABLE_PATH_SEGMENT_PATTERN` enforces `[A-Za-z0-9._-]` for download path segments

## Credential Security

- [ ] `CLOUD_STORAGE_SECRET` never appears in any log line
- [ ] Gemini API keys never passed as subprocess CLI args (use `build_gemini_env_overrides()`)
- [ ] `JWT_SECRET_KEY` not in any response or log
- [ ] bcrypt `rounds=12` (current) — consider 13 for new deployments
- [ ] Passwords logged nowhere (check `authenticate_user()`, `create_user()`)

## SQL Injection

- [ ] All DB queries use SQLAlchemy ORM (no f-string interpolation in queries)
- [ ] Raw `text()` used only in migrations with static SQL
- [ ] Alembic `op.execute()` uses parameterized queries where user input involved

## Subprocess Security

- [ ] Script paths (`PREPROCESS_SCRIPT_PATH`, `PROCESSOR_SCRIPT_PATH`) validated to exist before execution
- [ ] No user input passed as shell-interpolated arguments to subprocesses
- [ ] Gemini keys in subprocess environment — not args (confirmed in `build_gemini_env_overrides()`)
- [ ] Workspace directory uses execution ID as path segment (UUID, not user-supplied)

## CORS Configuration

- [ ] `CORS_ORIGINS` explicitly configured — not `["*"]` in production
- [ ] Origins loaded from env via `settings.CORS_ORIGINS`
- [ ] Credentials: `allow_credentials=True` — verify frontend sends cookies/headers correctly

## Email Security

- [ ] HTML email body uses `html.escape()` on user-derived content
- [ ] SMTP credentials not logged (`SMTP_USER`, `SMTP_PASSWORD`)
- [ ] Recipient email validated before send

## Signed URL Security

- [ ] Upload URLs: V4 (GCP) or presigned PUT (AWS) — time-limited
- [ ] Download URLs: signed, time-limited — never direct public object URLs
- [ ] `expiration`: upload=900s, download=600s — hardcoded in settings
- [ ] Content-Type not bound in signed URL (intentional — prevents 403 from browser variation)

## Review Checklist for Any New Feature

1. Does it return user data? → check tenant + user scoping
2. Does it write to storage? → use `build_execution_file_path()` for key construction
3. Does it call an external service? → check for timeout + retry config
4. Does it create a subprocess? → no user input in shell args
5. Does it log anything? → verify no secrets in the log message
6. Does it accept file upload? → check content type + size validation

## Known Acceptable Risk Areas

- `init_db.py` exists as deprecated file with `--force-deprecated` guard — acceptable
- Timing attack mitigation in `authenticate_user()` — dummy hash if user not found
- `admin123`/`user123` seed passwords — must be changed in production (documented)
