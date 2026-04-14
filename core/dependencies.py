"""
Dependency Injection
Service layer dependencies for FastAPI routes
"""
from typing import Annotated, Optional
from fastapi import Depends
from sqlalchemy.orm import Session

from db.database import get_db
from services.auth_service import AuthService
from services.execution_service import ExecutionService
from services.report_service import ReportService
from services.background_worker import BackgroundWorker


# Global worker instance (initialized in main.py lifespan)
_background_worker: Optional[BackgroundWorker] = None


def set_background_worker(worker: BackgroundWorker) -> None:
    """Set the global background worker instance"""
    global _background_worker
    _background_worker = worker


def get_background_worker() -> BackgroundWorker:
    """Dependency for BackgroundWorker"""
    if _background_worker is None:
        raise RuntimeError("BackgroundWorker not initialized")
    return _background_worker


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Dependency for AuthService"""
    return AuthService(db)


def get_execution_service(
    db: Session = Depends(get_db),
    worker: BackgroundWorker = Depends(get_background_worker)
) -> ExecutionService:
    """Dependency for ExecutionService"""
    return ExecutionService(db, worker)


def get_report_service(db: Session = Depends(get_db)) -> ReportService:
    """Dependency for ReportService"""
    return ReportService(db)


# Type aliases for cleaner route signatures
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ExecutionServiceDep = Annotated[ExecutionService, Depends(get_execution_service)]
ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
DBSessionDep = Annotated[Session, Depends(get_db)]
BackgroundWorkerDep = Annotated[BackgroundWorker, Depends(get_background_worker)]
