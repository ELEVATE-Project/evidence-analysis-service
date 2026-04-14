"""
Seed data initialization for Phase 1
Creates default users with properly hashed passwords
"""
import logging
from sqlalchemy.orm import Session
from services.auth_service import AuthService

logger = logging.getLogger(__name__)


def seed_default_users(db: Session) -> None:
    """
    Seed default users for Phase 1 development
    This should be called on application startup
    """
    auth_service = AuthService(db)
    
    # Default users configuration (loaded from env in production)
    default_users = [
        {
            "username": "admin",
            "email": "admin@shishalokam.com",
            "password": "admin123",
            "full_name": "System Administrator",
            "is_superuser": True,
            "tenant_code": "default",
            "organization_code": "default_code"
        },
        {
            "username": "program_designer",
            "email": "program_designer@shishalokam.com",
            "password": "user123",
            "full_name": "Program Designer",
            "is_superuser": False,
            "tenant_code": "default",
            "organization_code": "default_code"
        },
        {
            "username": "analyst",
            "email": "analyst@shishalokam.com",
            "password": "user123",
            "full_name": "Analyst",
            "is_superuser": False,
            "tenant_code": "default",
            "organization_code": "default_code"
        }
    ]
    
    for user_data in default_users:
        existing_user = auth_service.get_user_by_username(user_data["username"])
        
        if not existing_user:
            try:
                user = auth_service.create_user(
                    username=user_data["username"],
                    email=user_data["email"],
                    password=user_data["password"],
                    full_name=user_data["full_name"],
                    is_superuser=user_data["is_superuser"],
                    tenant_code=user_data["tenant_code"],
                    organization_code=user_data["organization_code"]
                )
                logger.info(f"Created default user: {user.username}")
            except Exception as e:
                logger.error(f"Failed to create user {user_data['username']}: {str(e)}")
                db.rollback()
        else:
            # Ensure existing seeded users always keep a valid bcrypt hash.
            if not auth_service.is_bcrypt_hash(existing_user.hashed_password):
                try:
                    existing_user.hashed_password = auth_service.get_password_hash(user_data["password"])
                    db.commit()
                    logger.warning(
                        f"Replaced invalid password format with bcrypt hash for user: {user_data['username']}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to repair password hash for user {user_data['username']}: {str(e)}"
                    )
                    db.rollback()
            else:
                logger.info(f"User {user_data['username']} already exists with valid bcrypt hash, skipping")
    
    logger.info("Seed data initialization completed")
