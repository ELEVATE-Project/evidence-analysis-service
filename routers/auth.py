"""
Authentication Router
Handles login, token generation, and user authentication
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from models.schemas import HTTPErrorResponse, MessageResponse, Token, UserResponse
from services.auth_service import AuthService
from core.dependencies import AuthServiceDep

router = APIRouter()


@router.post(
    "/login",
    response_model=Token,
    responses={
        401: {"model": HTTPErrorResponse, "description": "Incorrect username or password"},
    },
)
async def login(
    auth_service: AuthServiceDep,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """
    Login endpoint - returns JWT token
    Uses database authentication with proper password hashing
    """
    username = form_data.username.strip()
    user = auth_service.authenticate_user(username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return auth_service.create_token_response(user.username)


@router.post(
    "/refresh",
    response_model=Token,
    responses={
        401: {"model": HTTPErrorResponse, "description": "Unauthorized"},
    },
)
async def refresh_token(
    auth_service: AuthServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user)
):
    """Refresh access token for authenticated user"""
    return auth_service.create_token_response(current_user.username)


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": HTTPErrorResponse, "description": "Unauthorized"},
    },
)
async def get_current_user_info(
    current_user: UserResponse = Depends(AuthService.get_current_user)
):
    """Get current authenticated user information"""
    return current_user


@router.post("/logout", response_model=MessageResponse)
async def logout():
    """Logout endpoint (JWT is stateless, so this is informational)"""
    return MessageResponse(message="Successfully logged out")
