"""
FastAPI Application Entry Point
Evidence Analysis System - Phase 1
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from core.config import settings
from core.dependencies import set_background_worker
from db.database import engine, SessionLocal
from db.seed_data import seed_default_csv_source_types, seed_default_users
from models.schemas import HealthResponse, RootResponse
from services.background_worker import BackgroundWorker
from services.bootstrap import run_bootstrap
from routers import auth, cloud_services, config, criteria, entities, executions, notifications, reports

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _assert_migrations_current() -> None:
    """Fail fast if the database is not at the Alembic head revision.

    This prevents the application from running against a schema that is behind
    the codebase, which can cause silent data corruption or runtime errors.
    Always run `alembic upgrade head` before starting the application.
    """
    alembic_cfg = AlembicConfig("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    expected_heads = set(script.get_heads())

    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_heads = set(context.get_current_heads())

    if not current_heads:
        raise RuntimeError(
            "Database has no Alembic migrations applied. "
            "Run `alembic upgrade head` before starting the application."
        )

    if current_heads != expected_heads:
        raise RuntimeError(
            f"Database schema is out of date. "
            f"Applied: {current_heads}  Expected: {expected_heads}. "
            f"Run `alembic upgrade head` before starting the application."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup and cleanup on shutdown"""
    logger.info("Starting Evidence Analysis Service...")

    # Verify migrations are at head before doing anything else.
    # Raises RuntimeError with a clear message if the database is behind.
    _assert_migrations_current()
    logger.info("Database migrations are current")

    db = SessionLocal()
    try:
        seed_default_users(db)
        seed_default_csv_source_types(db)
        logger.info("Default seed data applied")
        await run_bootstrap(db)
    except Exception as e:
        logger.critical("Startup initialization failed: %s", e)
        raise
    finally:
        db.close()
    
    # Initialize background worker singleton
    worker = BackgroundWorker()
    set_background_worker(worker)
    logger.info("Background worker initialized")
    
    yield
    
    # Shutdown background worker
    logger.info("Shutting down background worker...")
    worker.shutdown()
    logger.info("Evidence Analysis Service shut down successfully")


# Initialize FastAPI app
app = FastAPI(
    title="Evidence Analysis API",
    description="API for Evidence Analysis System - Phase 1",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(executions.router, prefix="/api/v1/executions", tags=["Executions"])
app.include_router(cloud_services.router, prefix="/api/v1/cloud-services", tags=["Cloud Services"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(entities.router, prefix="/api/v1", tags=["Entities"])
app.include_router(config.router, prefix="/api/v1/config", tags=["Config"])
app.include_router(criteria.router, prefix="/api/v1/criteria", tags=["Criteria Validation"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])


@app.get("/", response_model=RootResponse, include_in_schema=False)
async def root():
    """Root endpoint"""
    return RootResponse(
        message="Evidence Analysis API",
        version="1.0.0",
        status="running",
    )


@app.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
