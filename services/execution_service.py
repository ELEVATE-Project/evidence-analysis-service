"""
Execution Service
Handles execution business logic, file management, and background processing
"""
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status
from uuid import UUID
from datetime import datetime
from typing import Optional
import hashlib

from models.execution import Execution
from models.schemas import ExecutionCreate, ExecutionResponse, ExecutionDetail, ExecutionList, StatusResponse
from services.storage_service import StorageService
from services.background_worker import BackgroundWorker


class ExecutionService:
    """Service for managing executions"""
    
    def __init__(self, db: Session, worker: BackgroundWorker):
        self.db = db
        self.storage_service = StorageService()
        self.worker = worker
    
    async def create_execution(
        self,
        execution_data: ExecutionCreate,
        input_file: UploadFile,
        questions_file: UploadFile,
        user_id: str
    ) -> ExecutionResponse:
        """
        Create a new execution with file uploads
        """
        # Validate file extensions
        if not input_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Input file must be a CSV file"
            )
        
        if not questions_file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Questions file must be a CSV file"
            )
        
        # Read and store files
        input_content = await input_file.read()
        questions_content = await questions_file.read()
        
        # Calculate checksums
        input_checksum = hashlib.md5(input_content).hexdigest()
        
        # Create execution record
        execution = Execution(
            name=execution_data.name,
            ai_model_id=execution_data.ai_model_id or "gemini-2.5-flash",
            program_ref_id=execution_data.program_ref_id,
            program_name=execution_data.program_name,
            state=execution_data.state,
            criterias_mode=execution_data.criterias_mode,
            threshold_config=execution_data.threshold_config,
            status='queued',
            created_by=user_id,
            input_file_size=len(input_content),
            input_file_checksum=input_checksum,
            questions_file_size=len(questions_content),
        )
        
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        
        # Upload files to storage
        try:
            input_url = await self.storage_service.upload_file(
                file_content=input_content,
                filename=f"{execution.id}/input_{input_file.filename}",
                content_type="text/csv"
            )
            
            questions_url = await self.storage_service.upload_file(
                file_content=questions_content,
                filename=f"{execution.id}/questions_{questions_file.filename}",
                content_type="text/csv"
            )
            
            # Update execution with file URLs
            execution.input_file_url = input_url
            execution.questions_file_url = questions_url
            execution.upload_completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(execution)
            
            # Submit to background worker
            self.worker.submit_job(execution.id)
            
        except Exception as e:
            # Rollback on error
            execution.status = 'failed'
            execution.failure_reason = f"File upload failed: {str(e)}"
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload files: {str(e)}"
            )
        
        return ExecutionResponse.model_validate(execution)
    
    def get_execution(self, execution_id: UUID, user_id: str) -> Optional[ExecutionDetail]:
        """Get execution by ID"""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()
        
        if not execution:
            return None
        
        return ExecutionDetail.model_validate(execution)
    
    def list_executions(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[str] = None
    ) -> ExecutionList:
        """List executions with pagination"""
        query = self.db.query(Execution).filter(Execution.created_by == user_id)
        
        if status_filter:
            query = query.filter(Execution.status == status_filter)
        
        total = query.count()
        
        executions = query.order_by(Execution.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        items = [ExecutionResponse.model_validate(e) for e in executions]
        
        return ExecutionList(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )
    
    def get_execution_status(self, execution_id: UUID, user_id: str) -> Optional[StatusResponse]:
        """Get real-time status of an execution"""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()
        
        if not execution:
            return None
        
        progress_percentage = None
        if execution.total_rows and execution.total_rows > 0:
            progress_percentage = (execution.processed_rows / execution.total_rows) * 100
        
        return StatusResponse(
            id=execution.id,
            status=execution.status,
            processed_rows=execution.processed_rows,
            total_rows=execution.total_rows,
            progress_percentage=progress_percentage,
            failure_reason=execution.failure_reason
        )
    
    def delete_execution(self, execution_id: UUID, user_id: str) -> bool:
        """Delete an execution (only if not running)"""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()
        
        if not execution:
            return False
        
        if execution.status == 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete running execution"
            )
        
        self.db.delete(execution)
        self.db.commit()
        
        return True
