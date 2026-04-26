"""
Notifications Router
Manual email notification APIs for executions
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.dependencies import ExecutionServiceDep
from models.schemas import (
    ExecutionNotificationResponse,
    HTTPErrorResponse,
    UserResponse,
)
from services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/executions/{execution_id}/email",
    response_model=ExecutionNotificationResponse,
    responses={
        400: {"model": HTTPErrorResponse, "description": "Recipient email is missing"},
        401: {"model": HTTPErrorResponse, "description": "Unauthorized"},
        404: {"model": HTTPErrorResponse, "description": "Execution not found"},
        409: {"model": HTTPErrorResponse, "description": "Execution not in terminal state"},
        502: {"model": HTTPErrorResponse, "description": "SMTP send failed after retries"},
        503: {"model": HTTPErrorResponse, "description": "SMTP not configured or notifications disabled"},
    },
)
async def send_execution_notification(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    force_resend: bool = Query(
        default=False,
        description="Force resend even if notification was already marked as sent.",
    ),
):
    """Send execution completion/failure email notification manually."""
    return execution_service.send_execution_notification(
        execution_id=execution_id,
        user_id=current_user.id,
        force_resend=force_resend,
    )

