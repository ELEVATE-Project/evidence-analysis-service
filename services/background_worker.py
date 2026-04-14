"""
Background Worker
Handles background processing using ThreadPoolExecutor
"""
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from uuid import UUID
import logging
import time
from datetime import datetime
from typing import Optional

from core.config import settings
from db.database import SessionLocal
from models.execution import Execution

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Background worker for processing executions"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_JOBS)
        logger.info(f"Background worker initialized with {settings.MAX_CONCURRENT_JOBS} workers")
    
    def submit_job(self, execution_id: UUID):
        """Submit execution job to worker pool"""
        logger.info(f"Submitting job for execution: {execution_id}")
        self.executor.submit(self._process_execution, execution_id)
    
    def _process_execution(self, execution_id: UUID):
        """
        Process execution in background thread
        This is a placeholder - actual processor integration will be added
        """
        # Create new DB session for this thread
        db = SessionLocal()
        
        try:
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if not execution:
                logger.error(f"Execution not found: {execution_id}")
                return
            
            # Update status to running
            execution.status = 'running'
            execution.processing_started_at = datetime.utcnow()
            execution.worker_id = f"worker_{time.time()}"
            db.commit()
            
            logger.info(f"Processing execution: {execution_id}")
            
            # Placeholder processing logic
            # TODO: Integrate actual processor from evidence-analysis-multithreaded
            time.sleep(5)  # Simulate processing
            
            # Update status to completed
            execution.status = 'completed'
            execution.processing_completed_at = datetime.utcnow()
            execution.completed_at = datetime.utcnow()
            execution.processed_rows = execution.total_rows or 100
            execution.total_rows = execution.total_rows or 100
            
            # Calculate average processing time
            if execution.processing_started_at and execution.processing_completed_at:
                duration = (execution.processing_completed_at - execution.processing_started_at).total_seconds()
                if execution.total_rows:
                    execution.average_processing_time = duration / execution.total_rows
            
            db.commit()
            
            logger.info(f"Completed execution: {execution_id}")
            
            # Send notification (TODO: implement email service)
            
        except Exception as e:
            logger.error(f"Failed to process execution {execution_id}: {str(e)}")
            
            # Update status to failed
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if execution:
                execution.status = 'failed'
                execution.failure_reason = str(e)
                execution.processing_completed_at = datetime.utcnow()
                db.commit()
        
        finally:
            db.close()
    
    def shutdown(self):
        """Shutdown worker pool gracefully"""
        logger.info("Shutting down background worker...")
        self.executor.shutdown(wait=True)
