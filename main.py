"""
FastAPI Application Entry Point
Evidence Analysis System - Phase 1
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

import sqlalchemy as sa
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


def _assert_db_exists() -> None:
    """Fail fast with an actionable message if the database itself does not exist.

    psycopg2 raises OperationalError with FATAL: database "X" does not exist
    when the DB is missing. We intercept that specific case and surface a clear
    setup instruction rather than a raw driver traceback.
    """
    import re
    from sqlalchemy.exc import OperationalError

    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except OperationalError as exc:
        msg = str(exc.orig) if exc.orig else str(exc)
        # psycopg2: 'FATAL:  database "X" does not exist'
        db_missing = "does not exist" in msg and "database" in msg.lower()
        if db_missing:
            # Extract the DB name from DATABASE_URL for the hint
            db_name_match = re.search(r"/([^/]+)$", str(engine.url))
            db_name = db_name_match.group(1) if db_name_match else "<dbname>"
            raise RuntimeError(
                f"\n\n"
                f"  DATABASE DOES NOT EXIST: '{db_name}'\n"
                f"\n"
                f"  The database named in DATABASE_URL does not exist on this PostgreSQL server.\n"
                f"  You must create it before running migrations or starting the application.\n"
                f"\n"
                f"  Fix:\n"
                f"    createdb -U postgres {db_name}\n"
                f"  Or in psql:\n"
                f"    sudo -u postgres psql -c \"CREATE DATABASE {db_name};\"\n"
                f"\n"
                f"  Then run migrations:\n"
                f"    alembic upgrade head\n"
                f"\n"
                f"  Current DATABASE_URL: {engine.url!r}\n"
            ) from None
        raise


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

    # Check the database exists before attempting Alembic state check.
    # Gives a clear, actionable error if DATABASE_URL points to a missing database.
    _assert_db_exists()

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
