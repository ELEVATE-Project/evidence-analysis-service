"""
Authentication Service
Handles user authentication, JWT token generation, and password hashing
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.config import settings
from db.database import get_db
from models.user import User
from models.schemas import TokenData, UserResponse

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class AuthService:
    """Authentication service for user management and JWT operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash"""
        if not hashed_password:
            return False

        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8")
            )
        except ValueError:
            # Invalid hash format in DB
            return False
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

    @staticmethod
    def is_bcrypt_hash(password_hash: str) -> bool:
        """Check whether stored password is a valid bcrypt hash"""
        if not password_hash or len(password_hash) != 60:
            return False

        if not password_hash.startswith(("$2a$", "$2b$", "$2y$")):
            return False

        try:
            # checkpw returns bool; invalid hash format raises ValueError.
            bcrypt.checkpw(b"format-check", password_hash.encode("utf-8"))
            return True
        except ValueError:
            return False
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username from database"""
        return self.db.query(User).filter(User.username == username).first()
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        is_superuser: bool = False,
        tenant_code: str = "default",
        organization_code: str = "default_code"
    ) -> User:
        """Create a new user with hashed password"""
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=self.get_password_hash(password),
            is_superuser=is_superuser,
            tenant_code=tenant_code,
            organization_code=organization_code,
            is_active=True
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password using proper password hashing"""
        user = self.get_user_by_username(username)
        
        if not user:
            # Prevent timing attacks by still hashing even if user doesn't exist
            self.get_password_hash(password + "dummy")
            return None
        
        if not user.is_active:
            return None
        
        # Use proper password verification with hash comparison
        if not self.verify_password(password, user.hashed_password):
            return None
        
        return user
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, datetime]:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.JWT_SECRET_KEY, 
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt, expire

    @staticmethod
    def create_token_response(username: str, expires_delta: Optional[timedelta] = None) -> dict:
        """Create token response payload with expiry metadata"""
        access_token, expires_at = AuthService.create_access_token(
            data={"sub": username},
            expires_delta=expires_delta
        )
        expires_in = int((expires_at - datetime.now(timezone.utc)).total_seconds())

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": max(expires_in, 0),
            "expires_at": expires_at
        }
    
    @staticmethod
    async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
    ) -> UserResponse:
        """Dependency to get current authenticated user from JWT token"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(
                token, 
                settings.JWT_SECRET_KEY, 
                algorithms=[settings.JWT_ALGORITHM]
            )
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except JWTError:
            raise credentials_exception
        
        # Get user from database
        user = db.query(User).filter(User.username == token_data.username).first()
        if user is None:
            raise credentials_exception
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        return UserResponse.model_validate(user)

    @staticmethod
    def verify_internal_access_token(x_internal_access_token: str) -> None:
        """Gate for internal/admin endpoints on a shared-secret header, checked against
        settings.INTERNAL_ACCESS_TOKEN. This sits alongside normal JWT auth
        (current_user), not in place of it — the endpoint still needs current_user for
        tenant/organization scoping and the updated_by audit trail; this is an extra
        factor on top, not a replacement for authentication.

        An unset INTERNAL_ACCESS_TOKEN always rejects (fails closed) rather than
        skipping the check, so a deployment that never configured this env var can't
        be bypassed with an empty header value.

        Plain function called from inside the route handler's own try/except, not a
        FastAPI Depends() — a Depends() raising HTTPException runs before the handler
        body and bypasses its try/except, so the error would skip the endpoint's
        StandardAPIResponse envelope and return FastAPI's bare {"detail": ...} shape
        instead, inconsistent with every other error this endpoint returns.
        """
        expected = settings.INTERNAL_ACCESS_TOKEN
        # Compare as bytes, not str: secrets.compare_digest raises TypeError for str
        # operands containing any non-ASCII character (Starlette decodes headers as
        # latin-1, so a malformed header can easily contain one) — that TypeError isn't
        # an HTTPException, so it would surface as a raw 500 instead of a clean 403.
        # Bytes comparison has no such restriction.
        if not expected or not secrets.compare_digest(
            x_internal_access_token.encode("utf-8"), expected.encode("utf-8")
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing internal access token.",
            )
