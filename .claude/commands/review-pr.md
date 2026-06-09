# Command: Review Pull Request

**Usage:** `/review-pr` (reviews current diff) or `/review-pr <PR description>`

Perform a structured PR review for the Evidence Analysis Service.

## Review Dimensions

### 1. Architecture Compliance

- [ ] Routers are thin (no business logic, no DB queries)
- [ ] Services own all DB access and business rules
- [ ] ORM models not imported in routers
- [ ] New services wired through `core/dependencies.py`
- [ ] DI uses `Annotated[Service, Depends(...)]` type aliases

### 2. Multi-tenancy Safety

- [ ] All queries returning user data filtered by `(tenant_code, organization_code)`
- [ ] `_resolve_scope(current_user)` pattern used for scope resolution
- [ ] No hardcoded `"default"` tenant in service queries

### 3. Schema Management

- [ ] No `Base.metadata.create_all()` anywhere
- [ ] Schema changes have Alembic migration
- [ ] Migration has complete `downgrade()`
- [ ] NOT NULL columns have `server_default`

### 4. Async Correctness

- [ ] Cloud SDK calls wrapped in `asyncio.to_thread()`
- [ ] No `asyncio.run()` inside async context
- [ ] DB-only methods are `def` (not `async def`)

### 5. Storage Safety

- [ ] File operations use `StorageService` methods
- [ ] No manual cloud URL construction
- [ ] Object keys via `build_execution_file_path()` or `_normalize_absolute_file_path()`

### 6. Error Handling

- [ ] No empty `except:` blocks
- [ ] `db.rollback()` on DB mutation failures
- [ ] Specific exception types, not bare `Exception`
- [ ] Errors logged before raising

### 7. Security

- [ ] No credentials in log messages
- [ ] Gemini keys via `get_gemini_tokens()` not direct env read
- [ ] Auth dependency on all new protected endpoints
- [ ] Input validated (file size, type, path)

### 8. Logging Quality

- [ ] `logging.getLogger(__name__)` per module
- [ ] `%s` formatting (not f-strings) in logger calls
- [ ] `key=value` structured format
- [ ] No PII or secrets logged

## Review Output Format

```
## PR Review: <title>

### ✅ Passes
- Architecture: routers thin, service owns logic
- Multi-tenancy: all queries properly scoped
- Migrations: complete with downgrade

### ⚠️ Concerns (non-blocking)
- Logger uses f-string at services/my_service.py:42
- Missing `from_attributes = True` in MyFeatureResponse

### ❌ Must Fix
- services/my_service.py:87 — DB query without tenant filter (data isolation breach)
- No migration for new `status_code` column

### Summary
<2-3 sentences on overall quality and readiness>
```
