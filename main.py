"""
FastAPI Application Entry Point
Evidence Analysis System - Phase 1
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from core.config import settings
from core.dependencies import set_background_worker
from db.database import engine, Base, SessionLocal
from db.seed_data import seed_default_csv_source_types, seed_default_users
from services.background_worker import BackgroundWorker
from routers import auth, cloud_services, config, entities, executions, reports

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup and cleanup on shutdown"""
    logger.info("Starting Evidence Analysis Service...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    # Seed default users
    db = SessionLocal()
    try:
        seed_default_users(db)
        seed_default_csv_source_types(db)
        logger.info("Default users seeded")
    except Exception as e:
        logger.error(f"Failed to seed users: {e}")
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


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Evidence Analysis API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
