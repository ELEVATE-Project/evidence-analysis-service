# Skill: Add API Endpoint

Add a new API endpoint following the thin-router, service-owned-logic pattern of this repository.

## Repository Constraints

- Routers: HTTP binding only. Parse request, delegate to service, return response. Zero business logic.
- Services: all DB queries, validation, orchestration.
- New endpoints require: Pydantic response schema, error response declarations, auth dependency.
- All endpoints that return user data must be scoped to `(tenant_code, organization_code)`.

## Step-by-Step Pattern

### 1. Define Pydantic Schemas (models/schemas.py)

```python
class MyFeatureRequest(BaseModel):
    name: str
    config: dict[str, Any]

class MyFeatureResponse(BaseModel):
    id: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True
```

Rules:
- Request schemas: suffix `Request`
- Response schemas: suffix `Response`
- Always include `from_attributes = True` for ORM-backed responses
- Use `Optional[T]` with default `None` for optional fields — not bare `T | None`

### 2. Add Service Method

```python
# In the appropriate service class (e.g., services/execution_service.py)
async def create_my_feature(
    self, request: MyFeatureRequest, current_user: UserResponse
) -> MyFeatureResponse:
    tenant_code, organization_code = self._resolve_scope(current_user)

    # DB mutation: always handle rollback
    try:
        record = MyModel(
            tenant_code=tenant_code,
            organization_code=organization_code,
            name=request.name,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
    except Exception as exc:
        self.db.rollback()
        logger.error("create_my_feature_failed  user=%s  error=%s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Failed to create feature") from exc

    return MyFeatureResponse.model_validate(record)
```

### 3. Add Route

```python
# In routers/executions.py (or appropriate router file)
@router.post(
    "/my-feature",
    response_model=MyFeatureResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": HTTPErrorResponse, "description": "Invalid request"},
        401: {"model": HTTPErrorResponse, "description": "Unauthorized"},
    },
)
async def create_my_feature(
    request: MyFeatureRequest,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """One-line description of what this does."""
    return await execution_service.create_my_feature(request, current_user)
```

Rules:
- Always declare expected error responses in `responses={}`
- Use `ExecutionServiceDep` (the `Annotated` alias) — never instantiate service directly
- Route docstring: one line, present tense, no "endpoint" or "API" in text
- `status_code` default is 200. Set `status.HTTP_201_CREATED` for POST-create.

### 4. Register Router (if new router file)

```python
# In main.py
app.include_router(my_router, prefix="/api/v1/my-feature", tags=["My Feature"])
```

## Validation Checklist

- [ ] Response schema has `from_attributes = True` if backed by ORM
- [ ] Service method scopes query by `tenant_code + organization_code`
- [ ] Route has `responses={4xx: {...}}` for expected errors
- [ ] Route uses `Depends(AuthService.get_current_user)` for protected endpoints
- [ ] Service uses `db.rollback()` on exception before re-raising
- [ ] No `import` of ORM models (e.g., `Execution`) in the router file
- [ ] Logger uses `%s` format strings, not f-strings
- [ ] New schema added to `models/schemas.py`, not inline in the route

## Anti-patterns

❌ `db.query(Execution).all()` in a router function
❌ `ExecutionService(db, worker)` manually in a route — use `ExecutionServiceDep`
❌ Missing `from_attributes = True` on response schema (will cause Pydantic validation error)
❌ Returning `{"message": "OK"}` without a typed schema
❌ Business logic (`if status == "completed": ...`) inside a route handler
