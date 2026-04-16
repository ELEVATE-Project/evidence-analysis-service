"""
Execution Service
Handles execution business logic, file management, and background processing
"""
import hashlib
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from models.execution import Execution
from models.schemas import (
    ExecutionCreate,
    ExecutionDetail,
    ExecutionList,
    ExecutionResponse,
    StatusResponse,
)
from services.background_worker import BackgroundWorker
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


class ExecutionService:
    """Service for managing executions"""
    
    def __init__(self, db: Session, worker: BackgroundWorker):
        self.db = db
        self.storage_service = StorageService()
        self.worker = worker

    @staticmethod
    def _to_float(value: Optional[Decimal]) -> Optional[float]:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _to_execution_response(execution: Execution) -> ExecutionResponse:
        """Build API response with safe fallbacks for nullable legacy fields."""
        return ExecutionResponse(
            id=execution.id,
            name=execution.name or "Untitled execution",
            status=execution.status or "queued",
            state=execution.state,
            district=execution.district,
            created_by=execution.created_by,
            created_at=execution.created_at or datetime.utcnow(),
            updated_at=execution.updated_at,
            completed_at=execution.completed_at,
            total_rows=execution.total_rows,
            processed_rows=execution.processed_rows,
            input_file_url=execution.input_file_url,
            questions_file_url=execution.questions_file_url,
            output_file_url=execution.output_file_url,
            failure_reason=execution.failure_reason,
            average_processing_time=ExecutionService._to_float(execution.average_processing_time),
            notification_sent=bool(execution.notification_sent) if execution.notification_sent is not None else False,
        )
    
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

        tenant_code = settings.DEFAULT_TENANT_CODE.strip()
        organization_code = settings.DEFAULT_ORGANIZATION_CODE.strip()
        if not tenant_code or not organization_code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Execution defaults are not configured"
            )
        
        # Create execution record
        execution = Execution(
            tenant_code=tenant_code,
            organization_code=organization_code,
            name=execution_data.name,
            ai_model_id=execution_data.ai_model_id or "gemini-2.5-flash",
            program_ref_id=execution_data.program_ref_id,
            program_name=execution_data.program_name,
            state=execution_data.state,
            district=execution_data.district,
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
        
        return self._to_execution_response(execution)
    
    def get_execution(self, execution_id: UUID, user_id: str) -> Optional[ExecutionDetail]:
        """Get execution by ID"""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()
        
        if not execution:
            return None
        
        return ExecutionDetail.model_validate(
            {
                **self._to_execution_response(execution).model_dump(),
                "tenant_code": execution.tenant_code,
                "organization_code": execution.organization_code,
                "ai_model_id": execution.ai_model_id,
                "program_ref_id": execution.program_ref_id,
                "program_name": execution.program_name,
                "criterias_mode": execution.criterias_mode,
                "criterias_config": execution.criterias_config,
                "threshold_config": execution.threshold_config,
                "actual_cost": self._to_float(execution.actual_cost),
                "estimated_cost": self._to_float(execution.estimated_cost),
                "input_file_size": execution.input_file_size,
                "questions_file_size": execution.questions_file_size,
                "output_file_size": execution.output_file_size,
                "worker_id": execution.worker_id,
                "retry_count": execution.retry_count,
                "processing_started_at": execution.processing_started_at,
                "processing_completed_at": execution.processing_completed_at,
            }
        )
    
    def list_executions(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[str] = None
    ) -> ExecutionList:
        """List executions with pagination"""
        if page < 1 or page_size < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="page and page_size must be greater than 0",
            )

        if page_size > 500:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="page_size cannot exceed 500",
            )

        try:
            query = self.db.query(Execution).filter(Execution.created_by == user_id)

            if status_filter:
                query = query.filter(Execution.status == status_filter)

            total = query.count()

            executions = query.order_by(Execution.created_at.desc()).offset(
                (page - 1) * page_size
            ).limit(page_size).all()
        except SQLAlchemyError as exc:
            logger.exception("Failed to query executions")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch executions. Please verify database schema/configuration.",
            ) from exc

        items: list[ExecutionResponse] = []
        for execution in executions:
            try:
                items.append(self._to_execution_response(execution))
            except ValidationError:
                logger.exception("Skipping malformed execution row: %s", getattr(execution, "id", "unknown"))

        return ExecutionList(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
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
