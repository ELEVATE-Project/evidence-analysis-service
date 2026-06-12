"""
Executions Router
Handles execution CRUD operations, signed upload flow, and status tracking
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from core.dependencies import ExecutionServiceDep
from models.schemas import (
    ExecutionCreateRequest,
    ExecutionDetail,
    ExecutionFileCompleteResponse,
    ExecutionFilePreviewResponse,
    ExecutionFileUploadUrlResponse,
    ExecutionList,
    ExecutionResponse,
    ExecutionValidationResponse,
    FileUploadUrlRequest,
    HTTPErrorResponse,
    ExecutionUploadInitRequest,
    ExecutionUploadInitResponse,
    ExecutionUpdate,
    StatusResponse,
    UserResponse,
)
from services.auth_service import AuthService

router = APIRouter()
logger = logging.getLogger(__name__)

EXECUTION_COMMON_ERROR_RESPONSES = {
    400: {"model": HTTPErrorResponse, "description": "Invalid execution request"},
    401: {"model": HTTPErrorResponse, "description": "Unauthorized"},
    404: {"model": HTTPErrorResponse, "description": "Execution not found"},
}


@router.post(
    "/",
    response_model=ExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def create_execution(
    request: ExecutionCreateRequest,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Step 1: Create analysis execution draft."""
    return await execution_service.create_execution_draft(request, current_user)


@router.post(
    "/{execution_id}/files/{file_type}/upload-url",
    response_model=ExecutionFileUploadUrlResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def get_file_upload_url(
    execution_id: UUID,
    file_type: str,
    request: FileUploadUrlRequest,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Step 2: Request signed upload URL for one file section."""
    return await execution_service.get_file_upload_url(
        execution_id=execution_id,
        file_type=file_type,
        request_data=request,
        user_id=current_user.id,
    )


@router.post(
    "/{execution_id}/files/{file_type}/complete",
    response_model=ExecutionFileCompleteResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def complete_file_upload(
    execution_id: UUID,
    file_type: str,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Step 2: Confirm uploaded file and detect rows/columns."""
    return await execution_service.complete_file_upload(
        execution_id=execution_id,
        file_type=file_type,
        user_id=current_user.id,
    )


@router.post(
    "/{execution_id}/files/{file_type}/upload",
    response_model=ExecutionFileCompleteResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def direct_upload_file(
    execution_id: UUID,
    file_type: str,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    file: UploadFile = File(...),
):
    """Fallback upload through backend when browser-to-cloud upload is blocked by CORS."""
    file_bytes = await file.read()
    return await execution_service.upload_file_direct(
        execution_id=execution_id,
        file_type=file_type,
        file_name=file.filename or "upload.csv",
        content_type=file.content_type,
        file_bytes=file_bytes,
        user_id=current_user.id,
    )


@router.post(
    "/{execution_id}/upload",
    response_model=ExecutionValidationResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def upload_both_files(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    input_file: UploadFile = File(..., description="Input data CSV file"),
    questions_file: UploadFile = File(..., description="Questions/criteria CSV file"),
):
    """
    Optimized endpoint: Upload both input and questions files in a single API call.
    Replaces the 3-step flow (get signed URLs, upload, complete) with one request.
    """
    # Read both files
    input_bytes = await input_file.read()
    questions_bytes = await questions_file.read()
    
    # Upload input file
    await execution_service.upload_file_direct(
        execution_id=execution_id,
        file_type="input",
        file_name=input_file.filename or "input.csv",
        content_type=input_file.content_type,
        file_bytes=input_bytes,
        user_id=current_user.id,
    )
    
    # Upload questions file
    await execution_service.upload_file_direct(
        execution_id=execution_id,
        file_type="questions",
        file_name=questions_file.filename or "questions.csv",
        content_type=questions_file.content_type,
        file_bytes=questions_bytes,
        user_id=current_user.id,
    )
    
    # Validate both files
    return await execution_service.validate_execution_files(
        execution_id=execution_id,
        user_id=current_user.id,
    )


@router.post(
    "/{execution_id}/validate",
    response_model=ExecutionValidationResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def validate_execution_files(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Step 3: Validate uploaded files against source-type config."""
    return await execution_service.validate_execution_files(
        execution_id=execution_id,
        user_id=current_user.id,
    )


@router.post(
    "/{execution_id}/start",
    response_model=ExecutionResponse,
    responses={
        **EXECUTION_COMMON_ERROR_RESPONSES,
        409: {"model": HTTPErrorResponse, "description": "Execution validation failed or execution not startable"},
    },
)
async def start_execution(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Step 4: Start analysis after successful validation."""
    return await execution_service.start_execution(
        execution_id=execution_id,
        user_id=current_user.id,
    )


@router.post(
    "/{execution_id}/rerun",
    response_model=ExecutionResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def rerun_execution(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Rerun a failed analysis after resetting runtime state."""
    return await execution_service.rerun_execution(
        execution_id=execution_id,
        user_id=current_user.id,
    )


@router.post(
    "/init-upload",
    response_model=ExecutionUploadInitResponse,
    status_code=status.HTTP_201_CREATED,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def init_execution_upload(
    request: ExecutionUploadInitRequest,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """
    Create a new execution and return signed upload URLs.
    Frontend should upload files directly to cloud storage and then call complete-upload.
    """
    return await execution_service.init_execution_upload(
        request_data=request,
        current_user=current_user,
    )

@router.post(
    "/{execution_id}/complete-upload",
    response_model=ExecutionResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def complete_execution_upload(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Validate uploaded files and queue execution in creation-only mode."""
    return await execution_service.complete_execution_upload(
        execution_id=execution_id,
        user_id=current_user.id,
    )


@router.get(
    "/",
    response_model=ExecutionList,
    responses={
        400: {"model": HTTPErrorResponse, "description": "Invalid list filters"},
        401: {"model": HTTPErrorResponse, "description": "Unauthorized"},
        500: {"model": HTTPErrorResponse, "description": "Failed to list executions"},
    },
)
async def list_executions(
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    status_filter: Optional[str] = None,
    status_group: Optional[str] = None,
    states: Optional[str] = Query(None, description="Comma-separated state names, e.g. Bihar,Haryana"),
    search_query: Optional[str] = None,
):
    """List executions with pagination and optional server-side filters."""
    states_filter = [s.strip() for s in states.split(",") if s.strip()] if states else None
    try:
        return await execution_service.list_executions(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            status_group=status_group,
            states_filter=states_filter,
            search_query=search_query,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error while listing executions for user=%s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list executions",
        )


@router.get(
    "/{execution_id}",
    response_model=ExecutionDetail,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def get_execution(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Get detailed information about a specific execution"""
    execution = execution_service.get_execution(execution_id, current_user.id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    return execution


@router.get(
    "/{execution_id}/files/{file_type}/preview",
    response_model=ExecutionFilePreviewResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def get_execution_file_preview(
    execution_id: UUID,
    file_type: str,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    limit: int = Query(10, ge=1, le=50),
):
    """Get read-only CSV preview for an uploaded execution file."""
    return await execution_service.get_execution_file_preview(
        execution_id=execution_id,
        file_type=file_type,
        user_id=current_user.id,
        limit=limit,
    )


@router.get(
    "/{execution_id}/status",
    response_model=StatusResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def get_execution_status(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Get real-time status of an execution"""
    status_info = execution_service.get_execution_status(execution_id, current_user.id)
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    return status_info


@router.patch(
    "/{execution_id}",
    response_model=ExecutionResponse,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def update_execution(
    execution_id: UUID,
    update_data: ExecutionUpdate,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Update an execution (only drafts can be updated)"""
    return execution_service.update_execution(
        execution_id=execution_id,
        update_data=update_data,
        user_id=current_user.id,
    )


@router.delete(
    "/{execution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=EXECUTION_COMMON_ERROR_RESPONSES,
)
async def delete_execution(
    execution_id: UUID,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Delete an execution (only if not in progress)."""
    success = execution_service.delete_execution(execution_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or cannot be deleted",
        )
    return None
