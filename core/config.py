"""
Application Configuration
Loads environment variables and application settings
"""
import json
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List

SERVICE_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = SERVICE_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Evidence Analysis System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str
    
    # JWT Authentication
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Execution defaults
    DEFAULT_TENANT_CODE: str = "default"
    DEFAULT_ORGANIZATION_CODE: str = "default_code"

    # Entity Management Service
    ENTITY_MGMT_BASE_URL: str = ""
    ENTITY_MGMT_TENANT_ID: str = "shikshalokam"
    ENTITY_MGMT_ORIGIN: str = "https://dev.elevate-sandbox.shikshalokam.org"
    ENTITY_MGMT_TIMEOUT_SECONDS: float = 10.0
    ENTITY_MGMT_RETRY_ATTEMPTS: int = 2
    ENTITY_MGMT_RETRY_BACKOFF_SECONDS: float = 0.5
    ENTITY_MGMT_CACHE_ENABLED: bool = True
    ENTITY_MGMT_STATES_CACHE_TTL_SECONDS: int = 900
    
    # File Storage
    STORAGE_TYPE: str = "gcp"  # "gcp", "s3", or "local"
    CLOUD_STORAGE_PROVIDER: str = "gcloud"  # "gcloud" or "aws"
    
    # GCP Storage
    CLOUD_STORAGE: str = "GCP"
    CLOUD_STORAGE_ACCOUNTNAME: str = ""
    CLOUD_STORAGE_BUCKETNAME: str = ""
    CLOUD_STORAGE_BUCKET_TYPE: str = "private"
    CLOUD_STORAGE_PROJECT: str = ""
    CLOUD_STORAGE_SECRET: str = ""
    
    # AWS S3 Storage
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    
    # Local Storage
    LOCAL_STORAGE_PATH: str = "./uploads"
    
    # AI Models (Gemini)
    GEMINI_API_KEY_1: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"
    
    # Email (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Evidence Analysis System"
    
    # Background Processing
    MAX_CONCURRENT_JOBS: int = 5
    WORKER_CHECK_INTERVAL: int = 5  # seconds

    # Celery + RabbitMQ queue processing
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"
    CELERY_RESULT_BACKEND: str = "rpc://"
    CELERY_TASK_QUEUE: str = "execution_queue"
    CELERY_TASK_ROUTING_KEY: str = "execution.process"
    CELERY_MAX_RETRIES: int = 3
    CELERY_RETRY_BACKOFF_SECONDS: int = 30
    CELERY_WORKER_CONCURRENCY: int = 2

    # Execution workspace + script runtime
    EXECUTION_WORKSPACE_ROOT: str = "/tmp/evidence_analysis/executions"
    EXECUTION_CLEANUP_ON_SUCCESS: bool = True
    PREPROCESS_SCRIPT_PATH: str = "scripts/pre-processor/1-pre-processor.py"
    PROCESSOR_SCRIPT_PATH: str = "scripts/processor/1-main-parallel-script.py"
    PROCESSOR_MAX_ROWS: int = 0
    PROCESSOR_RESUME_FROM_CHECKPOINT: bool = False
    
    # File Upload Limits
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: List[str] = [".csv"]
    SIGNED_UPLOAD_URL_EXPIRY_SECONDS: int = 900
    SIGNED_DOWNLOAD_URL_EXPIRY_SECONDS: int = 600

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_value(cls, value):
        """Allow bool-like and environment-style DEBUG values."""
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            raw = value.strip().lower()
            if raw in {"true", "1", "yes", "on", "debug", "development", "dev"}:
                return True
            if raw in {"false", "0", "no", "off", "release", "production", "prod"}:
                return False

        return value

    @field_validator("CORS_ORIGINS", "ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_list_settings(cls, value):
        """Accept JSON arrays or comma-separated env values."""
        if isinstance(value, list):
            return value

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []

            if raw.startswith("["):
                return json.loads(raw)

            return [item.strip() for item in raw.split(",") if item.strip()]

        return value
    
    class Config:
        env_file = str(ENV_FILE_PATH)
        case_sensitive = True


# Initialize settings
settings = Settings()

# Create local storage directory if using local storage
if settings.STORAGE_TYPE == "local":
    Path(settings.LOCAL_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
