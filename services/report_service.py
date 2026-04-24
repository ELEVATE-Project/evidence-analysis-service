"""
Report Service
Handles report generation, data retrieval, and export
"""
import csv
from io import StringIO
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from core.config import settings
from models.execution import Execution
from models.schemas import ReportDownloadResponse, ReportResponse
from services.storage_service import StorageService

logger = logging.getLogger(__name__)

REQUIRED_REPORT_COLUMNS = [
    "UUID",
    "Declared State",
    "District",
    "Block",
    "School Name",
    "Tasks",
    "Project ID",
    "Project start date of the user",
    "Project completion date of the user",
    "Relevance Tag",
]


class ReportCsvNotFoundError(Exception):
    """Raised when execution/report CSV is not available."""


class ReportCsvConflictError(Exception):
    """Raised when execution is not in report-ready state."""


class ReportCsvValidationError(Exception):
    """Raised when CSV content is invalid for report rendering."""


class ReportService:
    """Service for report operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.storage_service = StorageService()

    def _get_execution(self, execution_id: UUID, user_id: str) -> Optional[Execution]:
        return self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()
    
    def get_report(self, execution_id: UUID, user_id: str) -> Optional[ReportResponse]:
        """Get report data for completed execution"""
        execution = self._get_execution(execution_id, user_id)
        
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
    
    async def get_output_download_url(self, execution_id: UUID, user_id: str) -> Optional[ReportDownloadResponse]:
        """Return a short-lived signed download URL for the output CSV."""
        execution = self._get_execution(execution_id, user_id)
        
        if not execution or not execution.output_file_url:
            return None

        signed_download = await self.storage_service.generate_download_url(
            file_path=execution.output_file_url,
            expiration=settings.SIGNED_DOWNLOAD_URL_EXPIRY_SECONDS,
            response_filename=f"execution_{execution_id}_output.csv",
        )
        return ReportDownloadResponse(
            download_url=signed_download["url"],
            expires_in_seconds=signed_download["expires_in_seconds"],
        )

    async def get_output_csv_content(self, execution_id: UUID, user_id: str) -> str:
        """Download output CSV from cloud/local storage and validate report structure."""
        execution = self._get_execution(execution_id, user_id)
        if not execution:
            raise ReportCsvNotFoundError("Report not found")

        if execution.status != "completed":
            raise ReportCsvConflictError("Execution is not completed yet")

        if not execution.output_file_url:
            raise ReportCsvNotFoundError("Output CSV file is not available")

        file_bytes = await self.storage_service.download_file(execution.output_file_url)
        if not file_bytes:
            raise ReportCsvNotFoundError("Output CSV file not found in storage")

        csv_text: Optional[str] = None
        decode_errors: list[str] = []
        for encoding in ("utf-8-sig", "utf-8"):
            try:
                csv_text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError as exc:
                decode_errors.append(str(exc))

        if csv_text is None:
            logger.error(
                "Failed decoding report CSV for execution_id=%s: %s",
                execution_id,
                " | ".join(decode_errors),
            )
            raise ReportCsvValidationError("Output CSV is corrupted or not UTF-8 encoded")

        self._validate_report_csv_structure(csv_text)
        return csv_text

    def _validate_report_csv_structure(self, csv_text: str) -> None:
        try:
            reader = csv.DictReader(StringIO(csv_text))
        except csv.Error as exc:
            logger.error("Invalid CSV structure while reading header: %s", exc)
            raise ReportCsvValidationError("Invalid CSV structure")

        raw_fieldnames = list(reader.fieldnames or [])
        if not raw_fieldnames:
            raise ReportCsvValidationError("CSV header row is missing")

        normalized_headers: list[str] = []
        for index, name in enumerate(raw_fieldnames):
            cleaned = (name or "").strip()
            if index == 0:
                cleaned = cleaned.lstrip("\ufeff")
            normalized_headers.append(cleaned)

        missing_columns = [column for column in REQUIRED_REPORT_COLUMNS if column not in normalized_headers]
        if missing_columns:
            raise ReportCsvValidationError(
                f"Missing required CSV columns: {', '.join(missing_columns)}"
            )

        has_non_empty_row = False
        try:
            for row in reader:
                if any(str(value or "").strip() for value in row.values()):
                    has_non_empty_row = True
                    break
        except csv.Error as exc:
            logger.error("Invalid CSV row structure: %s", exc)
            raise ReportCsvValidationError("Invalid CSV structure")

        if not has_non_empty_row:
            raise ReportCsvValidationError("CSV contains no data rows")
    
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
