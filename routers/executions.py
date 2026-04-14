"""
Executions Router
Handles execution CRUD operations, file uploads, and status tracking
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from typing import Optional
from uuid import UUID

from models.schemas import (
    ExecutionCreate, ExecutionResponse, ExecutionDetail, 
    ExecutionList, StatusResponse, UserResponse
)
from services.auth_service import AuthService
from core.dependencies import ExecutionServiceDep

router = APIRouter()


@router.post("/", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_execution(
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    name: str = Form(...),
    input_file: UploadFile = File(...),
    questions_file: UploadFile = File(...),
    ai_model_id: Optional[str] = Form(None),
    program_ref_id: Optional[str] = Form(None),
    program_name: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    criterias_mode: Optional[str] = Form(None)
):
    """
    Create a new execution with file uploads
    - Uploads input CSV and questions CSV
    - Creates execution record
    - Triggers background processing
    """
    
    execution_data = ExecutionCreate(
        name=name,
        ai_model_id=ai_model_id,
        program_ref_id=program_ref_id,
        program_name=program_name,
        state=state,
        criterias_mode=criterias_mode
    )
    
    execution = await execution_service.create_execution(
        execution_data=execution_data,
        input_file=input_file,
        questions_file=questions_file,
        user_id=current_user.id
    )
    
    return execution


@router.get("/", response_model=ExecutionList)
async def list_executions(
    page: int = 1,
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None
):
    """
    List executions with pagination and filtering
    """(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status_filter=status
    )


@router.get("/{execution_id}", response_model=ExecutionDetail)
async def get_execution(
    execution_id: UUID,
    db: Session = Depends(get_db),
    execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user)
):
    """Get detailed information about a specific execution"""ion(execution_id, current_user.id)
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    return execution


@router.get("/{execution_id}/status", response_model=StatusResponse)
async def get_execution_status(
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(AuthService.get_current_user)
):execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user)
):
    """Get real-time status of an execution"""
    if not status_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    return status_info


@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(AuthService.get_current_user)
):execution_service: ExecutionServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user)
):
    """Delete an execution (only if not running)"""
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found or cannot be deleted"
        )
    
    return None
