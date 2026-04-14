"""
Application Configuration
Loads environment variables and application settings
"""
from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path


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
    
    # File Upload Limits
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_EXTENSIONS: List[str] = [".csv"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Initialize settings
settings = Settings()

# Create local storage directory if using local storage
if settings.STORAGE_TYPE == "local":
    Path(settings.LOCAL_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
