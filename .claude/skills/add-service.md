# Skill: Add a New Service

Add a properly wired service class following repository patterns.

## When You Need This

- New domain concept requiring DB access (e.g., `AuditService`)
- New external integration (e.g., `SlackNotificationService`)
- Extracting logic from an oversized service

## Step 1: Create the Service Class

```python
# services/my_service.py
"""
My Service
One-line description of what this service does.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from models.execution import Execution
from models.schemas import UserResponse

logger = logging.getLogger(__name__)


class MyService:
    """Service for <domain>."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _resolve_scope(current_user: UserResponse) -> tuple[str, str]:
        """Resolve tenant + org scope from the current user."""
        tenant_code = (
            (current_user.tenant_code or settings.DEFAULT_TENANT_CODE or "").strip()
        )
        organization_code = (
            (current_user.organization_code or settings.DEFAULT_ORGANIZATION_CODE or "").strip()
        )
        if not tenant_code or not organization_code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tenant/organization configuration is missing",
            )
        return tenant_code, organization_code

    def _get_record_or_404(self, record_id: str, user_id: str) -> Execution:
        record = self.db.query(Execution).filter(
            Execution.id == record_id,
            Execution.created_by == user_id,
        ).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Record not found")
        return record

    # ── Public API ───────────────────────────────────────────────────────

    def do_something(self, user_id: str, record_id: str) -> dict:
        """One-line description."""
        record = self._get_record_or_404(record_id, user_id)
        # ... logic ...
        return {"status": "done"}
```

## Step 2: Register in dependencies.py

```python
# core/dependencies.py

from services.my_service import MyService

def get_my_service(db: Session = Depends(get_db)) -> MyService:
    """Dependency for MyService."""
    return MyService(db)

MyServiceDep = Annotated[MyService, Depends(get_my_service)]
```

If the service has singleton-scoped state (caching, connections):
```python
_my_service: Optional[MyService] = None

def get_my_service() -> MyService:
    global _my_service
    if _my_service is None:
        _my_service = MyService.from_settings()  # or MyService(config)
    return _my_service
```

## Step 3: Use in Router

```python
from core.dependencies import MyServiceDep

@router.get("/my-resource/{id}")
async def get_my_resource(
    resource_id: str,
    my_service: MyServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    return my_service.do_something(current_user.id, resource_id)
```

## Step 4: Export from services/__init__.py (optional)

```python
# services/__init__.py
from .my_service import MyService

__all__ = [
    ...,
    "MyService",
]
```

## Patterns for Services with External Dependencies

```python
class ExternalIntegrationService:
    """Service wrapping an external API."""

    def __init__(self, client: MyExternalClient) -> None:
        self.client = client

    @classmethod
    def from_settings(cls) -> "ExternalIntegrationService":
        """Build from env settings — used by DI getter."""
        return cls(MyExternalClient(
            base_url=settings.EXTERNAL_API_URL,
            api_key=settings.EXTERNAL_API_KEY,
        ))
```

## Service with Cloud Storage

```python
class StorageBackedService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = StorageService()   # instantiated per request
```

## Validation Checklist

- [ ] Service in `services/my_service.py`
- [ ] `get_my_service()` in `core/dependencies.py`
- [ ] Type alias `MyServiceDep` in `core/dependencies.py`
- [ ] Singleton services initialized in `main.py` lifespan if startup validation needed
- [ ] `from __future__ import annotations` at top
- [ ] `logger = logging.getLogger(__name__)` at module level
- [ ] DB mutations wrapped in try/except with `db.rollback()` on failure
- [ ] All queries scoped by `tenant_code + organization_code` where user data is involved

## Anti-patterns

❌ `from services.my_service import MyService` directly in a route handler
❌ `db.query(...)` outside a service class
❌ Using `SessionLocal()` directly in a service — `db` is always injected
❌ Service calling another service's `db.commit()` — each service owns its own commits
