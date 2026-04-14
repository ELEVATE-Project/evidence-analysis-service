"""
Report Service
Handles report generation, data retrieval, and export
"""
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, Dict, Any
import pandas as pd
import logging

from models.execution import Execution
from models.schemas import ReportResponse
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


class ReportService:
    """Service for report operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.storage_service = StorageService()
    
    def get_report(self, execution_id: UUID, user_id: str) -> Optional[ReportResponse]:
        """Get report data for completed execution"""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()
        
        if not execution or execution.status != 'completed':
            return None
        
        # Load output CSV data
        output_data = self._load_output_data(execution.output_file_url)
        input_data = self._load_input_data(execution.input_file_url)
        
        metadata = {
            "execution_name": execution.name,
            "created_at": execution.created_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "total_rows": execution.total_rows,
            "processed_rows": execution.processed_rows,
            "average_processing_time": float(execution.average_processing_time) if execution.average_processing_time else None,
            "ai_model": execution.ai_model_id,
            "status": execution.status
        }
        
        return ReportResponse(
            execution_id=execution.id,
            input_data=input_data,
            output_data=output_data,
            metadata=metadata
        )
    
    def _load_output_data(self, file_url: str) -> Optional[Dict[str, Any]]:
        """Load and parse output CSV"""
        if not file_url:
            return None
        
        try:
            # This is a placeholder - actual implementation will parse CSV
            return {
                "file_url": file_url,
                "summary": "Output data summary"
            }
        except Exception as e:
            logger.error(f"Failed to load output data: {str(e)}")
            return None
    
    def _load_input_data(self, file_url: str) -> Optional[Dict[str, Any]]:
        """Load and parse input CSV"""
        if not file_url:
            return None
        
        try:
            return {
                "file_url": file_url,
                "summary": "Input data summary"
            }
        except Exception as e:
            logger.error(f"Failed to load input data: {str(e)}")
            return None
    
    def get_output_csv_path(self, execution_id: UUID, user_id: str) -> Optional[str]:
        """Get local path to output CSV file"""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()
        
        if not execution or not execution.output_file_url:
            return None
        
        # Return file path (download from S3 if needed)
        return execution.output_file_url
    
    def generate_html_report(self, execution_id: UUID, user_id: str) -> Optional[str]:
        """Generate HTML report (evidence-analysis UI parity)"""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()
        
        if not execution or execution.status != 'completed':
            return None
        
        # Placeholder HTML - will be enhanced with actual report template
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Execution Report - {execution.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #1976d2; color: white; padding: 20px; }}
                .content {{ margin-top: 20px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 15px; background: #f5f5f5; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{execution.name}</h1>
                <p>Status: {execution.status}</p>
            </div>
            <div class="content">
                <div class="metric">
                    <strong>Total Rows:</strong> {execution.total_rows}
                </div>
                <div class="metric">
                    <strong>Processed:</strong> {execution.processed_rows}
                </div>
                <div class="metric">
                    <strong>Avg Time:</strong> {execution.average_processing_time}s
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
