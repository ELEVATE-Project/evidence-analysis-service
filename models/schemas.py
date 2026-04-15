"""
Pydantic Schemas for Request/Response Validation
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


# ============ Authentication Schemas ============

class UserLogin(BaseModel):
    """Login request schema"""
    username: str
    password: str


class Token(BaseModel):
    """JWT token response schema"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: datetime


class TokenData(BaseModel):
    """Token payload data"""
    username: Optional[str] = None


class UserResponse(BaseModel):
    """User response schema"""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    tenant_code: Optional[str] = None
    organization_code: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============ Execution Schemas ============

class ExecutionCreate(BaseModel):
    """Schema for creating a new execution"""
    name: str = Field(..., min_length=1, max_length=255)
    ai_model_id: Optional[str] = None
    program_ref_id: Optional[str] = None
    program_name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    criterias_mode: Optional[str] = None
    threshold_config: Optional[Dict[str, Any]] = None


class ExecutionUpdate(BaseModel):
    """Schema for updating an execution"""
    name: Optional[str] = None
    status: Optional[str] = None
    failure_reason: Optional[str] = None
    processed_rows: Optional[int] = None
    total_rows: Optional[int] = None


class ExecutionResponse(BaseModel):
    """Schema for execution response"""
    id: UUID
    name: str
    status: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_rows: Optional[int] = None
    processed_rows: Optional[int] = None
    input_file_url: Optional[str] = None
    questions_file_url: Optional[str] = None
    output_file_url: Optional[str] = None
    failure_reason: Optional[str] = None
    average_processing_time: Optional[float] = None
    notification_sent: bool = False
    
    class Config:
        from_attributes = True


class ExecutionDetail(ExecutionResponse):
    """Detailed execution response with all fields"""
    tenant_code: Optional[str] = None
    organization_code: Optional[str] = None
    ai_model_id: Optional[str] = None
    program_ref_id: Optional[str] = None
    program_name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    criterias_mode: Optional[str] = None
    criterias_config: Optional[Dict[str, Any]] = None
    threshold_config: Optional[Dict[str, Any]] = None
    actual_cost: Optional[float] = None
    estimated_cost: Optional[float] = None
    input_file_size: Optional[int] = None
    questions_file_size: Optional[int] = None
    output_file_size: Optional[int] = None
    worker_id: Optional[str] = None
    retry_count: Optional[int] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ExecutionList(BaseModel):
    """Paginated execution list response"""
    total: int
    page: int
    page_size: int
    items: list[ExecutionResponse]


# ============ Report Schemas ============

class ReportResponse(BaseModel):
    """Report response schema"""
    execution_id: UUID
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


# ============ Status Schemas ============

class StatusResponse(BaseModel):
    """Execution status response"""
    id: UUID
    status: str
    processed_rows: Optional[int] = None
    total_rows: Optional[int] = None
    progress_percentage: Optional[float] = None
    failure_reason: Optional[str] = None
