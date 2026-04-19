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
    csv_type_id: str = Field(..., min_length=1, max_length=100)
    ai_model_id: Optional[str] = None
    program_ref_id: Optional[str] = None
    program_name: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    criterias_mode: Optional[str] = None
    threshold_config: Optional[Dict[str, Any]] = None


class FileUploadDescriptor(BaseModel):
    """Client-declared file metadata used before signed URL generation."""
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: Optional[str] = None
    size_bytes: int = Field(..., gt=0)


class ExecutionUploadInitRequest(ExecutionCreate):
    """Schema for creating execution and requesting signed upload URLs."""
    input_file: FileUploadDescriptor
    questions_file: FileUploadDescriptor


class SignedUrlPayload(BaseModel):
    """Signed URL payload for direct upload/download."""
    url: str
    method: str
    headers: Dict[str, str] = Field(default_factory=dict)
    expires_in_seconds: int


class ExecutionUploadInitResponse(BaseModel):
    """Execution creation response with signed upload URLs."""
    execution_id: UUID
    status: str
    input_upload: SignedUrlPayload
    questions_upload: SignedUrlPayload


class ExecutionCreateRequest(ExecutionCreate):
    """Step 1 request schema to create analysis execution draft."""
    pass


class FileUploadUrlRequest(BaseModel):
    """Request signed upload URL for a file section."""
    file: FileUploadDescriptor


class ExecutionFileUploadUrlResponse(BaseModel):
    """Signed upload URL response for input/questions file."""
    execution_id: UUID
    file_type: str
    upload: SignedUrlPayload


class ExecutionFileCompleteResponse(BaseModel):
    """File upload completion response with detected CSV metadata."""
    execution_id: UUID
    file_type: str
    uploaded: bool
    rows_detected: int
    columns_detected: list[str]


class FileValidationResult(BaseModel):
    """Validation result for one file section."""
    file_type: str
    valid: bool
    message: Optional[str] = None
    missing_columns: list[str] = Field(default_factory=list)
    rows_detected: Optional[int] = None
    columns_detected: Optional[list[str]] = None
    preview_rows: Optional[list[Dict[str, str]]] = None


class ExecutionValidationResponse(BaseModel):
    """Combined validation result for both files."""
    execution_id: UUID
    is_valid: bool
    input_file: FileValidationResult
    questions_file: FileValidationResult


class ExecutionFileCheckpointState(BaseModel):
    """Checkpoint state summary for one uploaded file."""
    uploaded: bool = False
    validated: bool = False
    rows_detected: Optional[int] = None
    columns_detected: list[str] = Field(default_factory=list)
    message: Optional[str] = None
    missing_columns: list[str] = Field(default_factory=list)
    updated_at: Optional[str] = None


class ExecutionFilePreviewResponse(BaseModel):
    """Read-only CSV preview for one uploaded file."""
    execution_id: UUID
    file_type: str
    rows_detected: int
    columns_detected: list[str]
    preview_rows: list[Dict[str, str]]


class ExecutionUpdate(BaseModel):
    """Schema for updating an execution"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    state: Optional[str] = None
    district: Optional[str] = None
    program_ref_id: Optional[str] = None
    program_name: Optional[str] = None
    criterias_mode: Optional[str] = None
    threshold_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    failure_reason: Optional[str] = None
    processed_rows: Optional[int] = None
    total_rows: Optional[int] = None


class ExecutionResponse(BaseModel):
    """Schema for execution response"""
    id: UUID
    name: str
    csv_type_id: Optional[str] = None
    status: str
    state: Optional[str] = None
    district: Optional[str] = None
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
    csv_type_id: Optional[str] = None
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
    upload_completed_at: Optional[datetime] = None
    checkpoint_data: Optional[Dict[str, Any]] = None
    input_file_status: Optional[ExecutionFileCheckpointState] = None
    questions_file_status: Optional[ExecutionFileCheckpointState] = None
    worker_id: Optional[str] = None
    error_logs: Optional[str] = None
    retry_count: Optional[int] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    notification_sent_at: Optional[datetime] = None
    
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


class ReportDownloadResponse(BaseModel):
    """Signed URL response for report download."""
    download_url: str
    expires_in_seconds: int


# ============ Status Schemas ============

class StatusResponse(BaseModel):
    """Execution status response"""
    id: UUID
    status: str
    processed_rows: Optional[int] = None
    total_rows: Optional[int] = None
    progress_percentage: Optional[float] = None
    failure_reason: Optional[str] = None


# ============ Cloud Services Schemas ============

class CloudSignedUrlRequestItem(BaseModel):
    """Grouped file names for a ref id (e.g., execution id)."""
    files: list[str] = Field(..., min_length=1)


class CloudSignedUrlRequest(BaseModel):
    """Common signed URL request format."""
    request: Dict[str, CloudSignedUrlRequestItem]
    ref: str = Field(..., min_length=1, max_length=100)


class CloudSignedUrlFilePayload(BaseModel):
    """Payload metadata returned with each file URL."""
    sourcePath: str
    fileType: Optional[str] = None


class CloudSignedUrlFileResponse(BaseModel):
    """Single signed URL response file entry."""
    file: str
    url: str
    downloadableUrl: str
    payload: CloudSignedUrlFilePayload
    cloudStorage: str


class CloudSignedUrlResultEntry(BaseModel):
    """Per-reference grouped file URL entries."""
    files: list[CloudSignedUrlFileResponse]


class CloudSignedUrlResponse(BaseModel):
    """Common signed URL response format."""
    responseCode: str
    message: str
    result: Dict[str, CloudSignedUrlResultEntry]
    meta: Dict[str, Any] = Field(default_factory=dict)
