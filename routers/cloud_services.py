"""
Cloud Services Router
Provides common signed URL APIs.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from core.dependencies import ExecutionServiceDep
from models.schemas import (
    CloudSignedUrlRequest,
    CloudSignedUrlResponse,
    ExecutionFileCompleteResponse,
    UserResponse,
)
from services.auth_service import AuthService

router = APIRouter()


@router.post("/getSignedUrl", response_model=CloudSignedUrlResponse)
async def get_signed_url(
    request: CloudSignedUrlRequest,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Generate signed URLs in common bulk request format."""
    return await execution_service.get_bulk_signed_upload_urls(
        request_data=request,
        user_id=current_user.id,
    )


@router.post("/upload", response_model=ExecutionFileCompleteResponse)
async def upload_file(
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    execution_id: UUID = Form(...),
    file_type: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload execution files via common cloud-services route (backend-upload fallback)."""
    file_bytes = await file.read()
    return await execution_service.upload_file_direct(
        execution_id=execution_id,
        file_type=file_type,
        file_name=file.filename or "upload.csv",
        content_type=file.content_type,
        file_bytes=file_bytes,
        user_id=current_user.id,
    )
