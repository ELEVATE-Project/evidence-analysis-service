"""
Criteria validation router.
Provides interactive one-off evidence criteria validation endpoints.
"""
from fastapi import APIRouter, Depends

from core.dependencies import CriteriaValidationServiceDep
from models.schemas import (
    CriteriaValidationRequest,
    CriteriaValidationResponse,
    UserResponse,
)
from services.auth_service import AuthService

router = APIRouter()


@router.post("/validate", response_model=CriteriaValidationResponse)
async def validate_criteria(
    request: CriteriaValidationRequest,
    criteria_validation_service: CriteriaValidationServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Validate ad-hoc evidence criteria against an evidence image URL."""
    return await criteria_validation_service.validate_criteria(
        request_data=request,
        user_id=current_user.id,
    )
