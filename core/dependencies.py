"""
Dependency Injection
Service layer dependencies for FastAPI routes
"""
from typing import Annotated, Optional
from fastapi import Depends
from sqlalchemy.orm import Session

from db.database import get_db
from services.auth_service import AuthService
from services.criteria_validation_service import CriteriaValidationService
from services.config_service import ConfigService
from services.entity_service import EntityService
from services.execution_service import ExecutionService
from services.report_service import ReportService
from services.background_worker import BackgroundWorker


# Global worker instance (initialized in main.py lifespan)
_background_worker: Optional[BackgroundWorker] = None
_entity_service: Optional[EntityService] = None
_criteria_validation_service: Optional[CriteriaValidationService] = None


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


def get_config_service(db: Session = Depends(get_db)) -> ConfigService:
    """Dependency for ConfigService."""
    return ConfigService(db)


def get_entity_service() -> EntityService:
    """Dependency for EntityService singleton (supports in-memory caching)."""
    global _entity_service
    if _entity_service is None:
        _entity_service = EntityService.from_settings()
    return _entity_service


def get_criteria_validation_service() -> CriteriaValidationService:
    """Dependency for CriteriaValidationService singleton."""
    global _criteria_validation_service
    if _criteria_validation_service is None:
        _criteria_validation_service = CriteriaValidationService()
    return _criteria_validation_service


# Type aliases for cleaner route signatures
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ExecutionServiceDep = Annotated[ExecutionService, Depends(get_execution_service)]
ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
ConfigServiceDep = Annotated[ConfigService, Depends(get_config_service)]
CriteriaValidationServiceDep = Annotated[CriteriaValidationService, Depends(get_criteria_validation_service)]
EntityServiceDep = Annotated[EntityService, Depends(get_entity_service)]
DBSessionDep = Annotated[Session, Depends(get_db)]
BackgroundWorkerDep = Annotated[BackgroundWorker, Depends(get_background_worker)]
