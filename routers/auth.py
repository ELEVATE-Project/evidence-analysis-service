"""
Authentication Router
Handles login, token generation, and user authentication
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from models.schemas import Token, UserResponse
from services.auth_service import AuthService
from core.dependencies import AuthServiceDep

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post("/login", response_model=Token)
async def login(
    auth_service: AuthServiceDep,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Login endpoint - returns JWT token
    Uses database authentication with proper password hashing
    """
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_access_token(data={"sub": user.username})
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(AuthService.get_current_user)
):
    """Get current authenticated user information"""
    return current_user


@router.post("/logout")
async def logout():
    """Logout endpoint (JWT is stateless, so this is informational)"""
    return {"message": "Successfully logged out"}
