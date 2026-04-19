"""
Execution Service
Handles execution business logic, file management, and background processing
"""
import csv
import io
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from models.csv_source_type import CsvSourceType
from models.execution import Execution
from models.schemas import (
    CloudSignedUrlRequest,
    CloudSignedUrlResponse,
    ExecutionCreateRequest,
    ExecutionDetail,
    ExecutionFileCompleteResponse,
    ExecutionFileUploadUrlResponse,
    ExecutionList,
    ExecutionResponse,
    ExecutionValidationResponse,
    ExecutionUploadInitRequest,
    ExecutionUploadInitResponse,
    FileUploadUrlRequest,
    FileValidationResult,
    SignedUrlPayload,
    StatusResponse,
    UserResponse,
)
from services.background_worker import BackgroundWorker
from services.storage_service import StorageService

logger = logging.getLogger(__name__)

_ALLOWED_CSV_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
}

_FILE_TYPE_HINTS = {
    "questions": ("question", "questions", "criteria", "checklist"),
    "input": ("input", "evidence", "data"),
}


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
            csv_type_id=execution.csv_type_id,
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

    def _validate_file_descriptor(self, file_name: str, size_bytes: int, content_type: Optional[str], label: str) -> tuple[str, str]:
        safe_file_name = self.storage_service.sanitize_filename(file_name)
        extension = Path(safe_file_name).suffix.lower()
        allowed_extensions = {ext.lower() for ext in settings.ALLOWED_EXTENSIONS}

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} must be one of: {', '.join(sorted(allowed_extensions))}",
            )

        if size_bytes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} size must be greater than 0 bytes",
            )

        if size_bytes > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{label} exceeds max size of {settings.MAX_UPLOAD_SIZE} bytes"
                ),
            )

        normalized_content_type = (content_type or "text/csv").strip().lower()
        if normalized_content_type not in _ALLOWED_CSV_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{label} content type '{normalized_content_type}' is not allowed"
                ),
            )

        return safe_file_name, normalized_content_type

    def _validate_file_name_for_signed_url(self, file_name: str, label: str) -> str:
        """Validate file name when size/content-type are not provided."""
        safe_file_name = self.storage_service.sanitize_filename(file_name)
        extension = Path(safe_file_name).suffix.lower()
        allowed_extensions = {ext.lower() for ext in settings.ALLOWED_EXTENSIONS}

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} must be one of: {', '.join(sorted(allowed_extensions))}",
            )

        return safe_file_name

    @staticmethod
    def _infer_file_type(file_name: str, used_types: set[str]) -> str:
        lower_name = (file_name or "").strip().lower()

        if "questions" not in used_types:
            if any(token in lower_name for token in _FILE_TYPE_HINTS["questions"]):
                return "questions"
        if "input" not in used_types:
            if any(token in lower_name for token in _FILE_TYPE_HINTS["input"]):
                return "input"

        if "input" not in used_types:
            return "input"
        if "questions" not in used_types:
            return "questions"

        return "questions"

    def _validate_uploaded_metadata(self, metadata: dict, label: str) -> None:
        size_bytes = int(metadata.get("size_bytes", 0))
        if size_bytes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} was not uploaded or is empty",
            )

        if size_bytes > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} exceeds max size of {settings.MAX_UPLOAD_SIZE} bytes",
            )

        content_type = metadata.get("content_type")
        if content_type:
            normalized_content_type = content_type.strip().lower()
            if normalized_content_type not in _ALLOWED_CSV_CONTENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"{label} content type '{normalized_content_type}' is not allowed"
                    ),
                )

    @staticmethod
    def _resolve_scope(current_user: UserResponse) -> tuple[str, str]:
        tenant_code = (current_user.tenant_code or settings.DEFAULT_TENANT_CODE or "").strip()
        organization_code = (current_user.organization_code or settings.DEFAULT_ORGANIZATION_CODE or "").strip()
        if not tenant_code or not organization_code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Execution defaults are not configured",
            )
        return tenant_code, organization_code

    def _get_csv_source_type(self, tenant_code: str, organization_code: str, type_key: str) -> Optional[CsvSourceType]:
        normalized_type_key = (type_key or "").strip()
        if not normalized_type_key:
            return None

        return (
            self.db.query(CsvSourceType)
            .filter(
                CsvSourceType.tenant_code == tenant_code,
                CsvSourceType.organization_code == organization_code,
                CsvSourceType.type_key == normalized_type_key,
                CsvSourceType.is_active.is_(True),
            )
            .first()
        )

    @staticmethod
    def _flatten_column_mapping_headers(value: Any) -> list[str]:
        headers: list[str] = []
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                headers.append(normalized)
            return headers

        if isinstance(value, dict):
            for nested_value in value.values():
                headers.extend(ExecutionService._flatten_column_mapping_headers(nested_value))
            return headers

        if isinstance(value, list):
            for nested_value in value:
                headers.extend(ExecutionService._flatten_column_mapping_headers(nested_value))
            return headers

        return headers

    @staticmethod
    def _decode_csv_bytes(file_bytes: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to decode CSV file. Please upload a UTF-8 compatible CSV.",
        )

    @classmethod
    def _extract_headers_and_row_count(cls, file_bytes: bytes, label: str) -> tuple[list[str], int]:
        decoded_content = cls._decode_csv_bytes(file_bytes)
        reader = csv.reader(io.StringIO(decoded_content))

        try:
            raw_headers = next(reader)
        except StopIteration as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} is empty.",
            ) from exc

        headers = [header.strip() for header in raw_headers if header and header.strip()]
        if not headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} is missing a valid header row.",
            )

        row_count = 0
        for row in reader:
            if any((cell or "").strip() for cell in row):
                row_count += 1

        return headers, row_count

    @classmethod
    def _parse_csv_preview(
        cls,
        file_bytes: bytes,
        label: str,
        *,
        preview_limit: int = 10,
        tracked_column: Optional[str] = None,
    ) -> tuple[list[str], int, list[dict[str, str]], set[str]]:
        decoded_content = cls._decode_csv_bytes(file_bytes)
        reader = csv.reader(io.StringIO(decoded_content))

        try:
            raw_headers = next(reader)
        except StopIteration as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} is empty.",
            ) from exc

        header_cells = [(cell or "").strip() for cell in raw_headers]
        headers: list[str] = []
        header_to_index: dict[str, int] = {}
        for index, header in enumerate(header_cells):
            if not header or header in header_to_index:
                continue
            headers.append(header)
            header_to_index[header] = index

        if not headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{label} is missing a valid header row.",
            )

        row_count = 0
        preview_rows: list[dict[str, str]] = []
        tracked_values: set[str] = set()
        tracked_key = (tracked_column or "").strip()

        for row in reader:
            if not any((cell or "").strip() for cell in row):
                continue

            row_count += 1
            row_payload: dict[str, str] = {}
            for header in headers:
                index = header_to_index.get(header, -1)
                value = (row[index] or "").strip() if index >= 0 and index < len(row) else ""
                row_payload[header] = value

            if len(preview_rows) < preview_limit:
                preview_rows.append(row_payload)

            if tracked_key:
                tracked_value = row_payload.get(tracked_key, "").strip()
                if tracked_value:
                    tracked_values.add(tracked_value)

        return headers, row_count, preview_rows, tracked_values

    def _collect_required_input_headers(self, source_type: CsvSourceType) -> list[str]:
        required_headers = self._flatten_column_mapping_headers(source_type.column_mappings or {})

        evidence_columns = source_type.evidence_columns or []
        if isinstance(evidence_columns, list):
            for evidence_config in evidence_columns:
                if not isinstance(evidence_config, dict):
                    continue
                column_name = str(evidence_config.get("column", "")).strip()
                if column_name:
                    required_headers.append(column_name)

        # Preserve order while removing duplicates.
        unique_headers: list[str] = []
        seen: set[str] = set()
        for header in required_headers:
            normalized = header.strip()
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_headers.append(normalized)

        return unique_headers

    def _validate_input_csv_metadata(
        self,
        headers: list[str],
        row_count: int,
        source_type: CsvSourceType,
    ) -> None:
        header_set = set(headers)

        max_rows = source_type.max_rows_per_upload
        if isinstance(max_rows, int) and max_rows > 0 and row_count > max_rows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input file exceeds max rows limit ({max_rows}).",
            )

        required_headers = self._collect_required_input_headers(source_type)
        missing_headers = [header for header in required_headers if header not in header_set]
        if missing_headers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input file is missing required columns: {', '.join(missing_headers)}",
            )

    def _validate_input_csv_against_source(
        self,
        input_file_bytes: bytes,
        source_type: CsvSourceType,
    ) -> None:
        headers, row_count = self._extract_headers_and_row_count(input_file_bytes, "Input file")
        self._validate_input_csv_metadata(headers, row_count, source_type)

    @staticmethod
    def _resolve_required_question_columns(source_type: CsvSourceType) -> list[str]:
        question_config = source_type.question_config or {}
        if not isinstance(question_config, dict):
            question_config = {}

        mandatory_columns = question_config.get("mandatory_columns", [])
        if not isinstance(mandatory_columns, list):
            mandatory_columns = []

        evidence_context_config = source_type.evidence_context_config or {}
        title_column = str(evidence_context_config.get("title_column", "")).strip()

        required_columns: list[str] = []
        for column in mandatory_columns:
            column_str = str(column).strip()
            if not column_str:
                continue
            if column_str == "evidence_context_config.title_column" and title_column:
                required_columns.append(title_column)
                continue
            required_columns.append(column_str)

        return required_columns

    def _validate_questions_csv_metadata(
        self,
        headers: list[str],
        source_type: CsvSourceType,
    ) -> None:
        header_set = set(headers)
        required_columns = self._resolve_required_question_columns(source_type)
        missing_columns = [column for column in required_columns if column not in header_set]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Questions file is missing mandatory columns: {', '.join(missing_columns)}",
            )

    def _validate_questions_csv_against_source(
        self,
        questions_file_bytes: bytes,
        source_type: CsvSourceType,
    ) -> None:
        headers, _ = self._extract_headers_and_row_count(questions_file_bytes, "Questions file")
        self._validate_questions_csv_metadata(headers, source_type)

    @staticmethod
    def _validate_tasks_cross_reference_from_values(input_tasks: set[str], questions_tasks: set[str]) -> None:
        missing_tasks = questions_tasks - input_tasks
        if not missing_tasks:
            return

        missing_list = list(missing_tasks)[:5]
        missing_display = ", ".join(missing_list)
        if len(missing_tasks) > 5:
            missing_display += f" (and {len(missing_tasks) - 5} more)"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Questions file references tasks not found in input file: {missing_display}",
        )

    def _validate_tasks_cross_reference(
        self,
        input_file_bytes: bytes,
        questions_file_bytes: bytes,
        source_type: CsvSourceType,
    ) -> None:
        """Validate that tasks mentioned in questions CSV exist in input CSV."""
        evidence_context_config = source_type.evidence_context_config or {}
        title_column = evidence_context_config.get("title_column", "")
        
        if not title_column:
            return  # No title column configured, skip cross-validation

        _, _, _, input_tasks = self._parse_csv_preview(
            input_file_bytes,
            "Input file",
            tracked_column=title_column,
        )
        _, _, _, questions_tasks = self._parse_csv_preview(
            questions_file_bytes,
            "Questions file",
            tracked_column=title_column,
        )
        self._validate_tasks_cross_reference_from_values(input_tasks, questions_tasks)

    @staticmethod
    def _extract_missing_columns_from_detail(detail: str) -> list[str]:
        if ":" not in detail:
            return []
        missing = detail.split(":", 1)[1].strip()
        return [item.strip() for item in missing.split(",") if item.strip()]

    @staticmethod
    def _to_user_friendly_validation_message(detail: str, file_label: str) -> str:
        normalized = (detail or "").strip()
        if not normalized:
            return f"We found an issue in the {file_label}. Please review and re-upload the file."

        normalized_lower = normalized.lower()
        file_label_lower = file_label.lower()

        if normalized.endswith("is missing.") and normalized_lower.startswith(file_label_lower):
            return f"{file_label} is missing. Please upload it and try again."

        if "missing required columns:" in normalized_lower or "missing mandatory columns:" in normalized_lower:
            missing_columns = ExecutionService._extract_missing_columns_from_detail(normalized)
            if len(missing_columns) == 1:
                return f"Missing required column: {missing_columns[0]}. Please fix the CSV and re-upload."
            if missing_columns:
                return f"Missing required columns: {', '.join(missing_columns)}. Please fix the CSV and re-upload."
            return "Required columns are missing. Please fix the CSV and re-upload."

        if "references tasks not found in input file:" in normalized_lower:
            missing_tasks = normalized.split(":", 1)[1].strip() if ":" in normalized else ""
            if missing_tasks:
                return (
                    "Some tasks in the Criteria file were not found in the Input file: "
                    f"{missing_tasks}. Please fix and re-upload."
                )
            return "Some tasks in the Criteria file were not found in the Input file. Please fix and re-upload."

        if "could not be downloaded" in normalized_lower or "could not be read" in normalized_lower:
            return f"We could not read the {file_label_lower}. Please re-upload the file and try again."

        if "unable to decode csv file" in normalized_lower:
            return f"The {file_label_lower} is not UTF-8 compatible. Please upload a UTF-8 CSV file."

        if normalized_lower.endswith("is empty."):
            return f"The {file_label_lower} is empty. Please upload a CSV with headers and data."

        if "missing a valid header row" in normalized_lower:
            return f"The {file_label_lower} header row is missing or invalid. Please fix and re-upload."

        if "exceeds max rows limit" in normalized_lower:
            return (
                f"The {file_label_lower} has more rows than allowed. "
                "Please reduce the row count and re-upload."
            )

        return f"We found an issue while validating the {file_label_lower}. Please review and re-upload."

    @staticmethod
    def _validate_scope_metadata(
        request_data: Any,
        source_type: CsvSourceType,
    ) -> None:
        if source_type.has_geo and not (request_data.state or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="State is required for the selected CSV source type.",
            )

    def _mark_execution_failed(self, execution: Execution, reason: str) -> None:
        execution.status = "failed"
        execution.failure_reason = reason
        self.db.commit()

    @staticmethod
    def _ensure_not_started_for_file_changes(execution: Execution) -> None:
        """Allow file uploads/validation changes only before analysis is started."""
        normalized_status = (execution.status or "").strip().lower()
        if normalized_status in {"draft", "validated"}:
            return

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Analysis has already started or ended. "
                "You can re-upload files only before starting analysis."
            ),
        )

    @staticmethod
    def _get_file_path_by_type(execution: Execution, file_type: str) -> Optional[str]:
        if file_type == "input":
            return execution.input_file_url
        if file_type == "questions":
            return execution.questions_file_url
        return None

    @staticmethod
    def _set_file_path_by_type(execution: Execution, file_type: str, file_path: str) -> None:
        if file_type == "input":
            execution.input_file_url = file_path
            return
        if file_type == "questions":
            execution.questions_file_url = file_path
            return
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type.",
        )

    @staticmethod
    def _set_file_size_by_type(execution: Execution, file_type: str, size_bytes: int) -> None:
        if file_type == "input":
            execution.input_file_size = size_bytes
            return
        if file_type == "questions":
            execution.questions_file_size = size_bytes
            return
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type.",
        )

    @staticmethod
    def _checkpoint(execution: Execution) -> dict[str, Any]:
        checkpoint = execution.checkpoint_data if isinstance(execution.checkpoint_data, dict) else {}
        files = checkpoint.get("files")
        if not isinstance(files, dict):
            files = {}
        for file_type in ("input", "questions"):
            file_state = files.get(file_type)
            if not isinstance(file_state, dict):
                files[file_type] = {}
        checkpoint["files"] = files
        return checkpoint

    def _update_file_checkpoint(
        self,
        execution: Execution,
        *,
        file_type: str,
        uploaded: Optional[bool] = None,
        validated: Optional[bool] = None,
        rows_detected: Optional[int] = None,
        columns_detected: Optional[list[str]] = None,
        message: Optional[str] = None,
        missing_columns: Optional[list[str]] = None,
    ) -> None:
        checkpoint = self._checkpoint(execution)
        file_checkpoint = checkpoint["files"][file_type]

        if uploaded is not None:
            file_checkpoint["uploaded"] = uploaded
        if validated is not None:
            file_checkpoint["validated"] = validated
        if rows_detected is not None:
            file_checkpoint["rows_detected"] = rows_detected
        if columns_detected is not None:
            file_checkpoint["columns_detected"] = columns_detected
        if message is not None:
            file_checkpoint["message"] = message
        if missing_columns is not None:
            file_checkpoint["missing_columns"] = missing_columns

        file_checkpoint["updated_at"] = datetime.utcnow().isoformat()
        execution.checkpoint_data = checkpoint

    def _get_execution_or_404(self, execution_id: UUID, user_id: str) -> Execution:
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id,
        ).first()

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found",
            )
        return execution

    async def create_execution_draft(
        self,
        request_data: ExecutionCreateRequest,
        current_user: UserResponse,
    ) -> ExecutionResponse:
        """Step 1: create analysis draft only."""
        tenant_code, organization_code = self._resolve_scope(current_user)
        source_type = self._get_csv_source_type(
            tenant_code=tenant_code,
            organization_code=organization_code,
            type_key=request_data.csv_type_id,
        )
        if not source_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or inactive csv_type_id for this tenant/organization.",
            )
        self._validate_scope_metadata(request_data, source_type)

        execution = Execution(
            tenant_code=tenant_code,
            organization_code=organization_code,
            name=request_data.name,
            csv_type_id=source_type.type_key,
            ai_model_id=request_data.ai_model_id or "gemini-2.5-flash",
            program_ref_id=request_data.program_ref_id,
            program_name=request_data.program_name,
            state=request_data.state,
            district=request_data.district,
            criterias_mode=request_data.criterias_mode,
            threshold_config=request_data.threshold_config,
            status="draft",
            created_by=current_user.id,
            checkpoint_data={"files": {"input": {}, "questions": {}}},
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return self._to_execution_response(execution)

    async def get_bulk_signed_upload_urls(
        self,
        request_data: CloudSignedUrlRequest,
        user_id: str,
    ) -> CloudSignedUrlResponse:
        """
        Generate signed upload URLs in common cloud-services format.
        Contract:
        {
          "request": { "<executionId>": { "files": ["a.csv", "b.csv"] } },
          "ref": "execution"
        }
        """
        if (request_data.ref or "").strip().lower() != "execution":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported ref. Use ref=execution.",
            )

        result: dict[str, dict[str, Any]] = {}
        for execution_key, request_item in request_data.request.items():
            try:
                execution_uuid = UUID(str(execution_key))
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid execution id: {execution_key}",
                ) from exc

            execution = self._get_execution_or_404(execution_uuid, user_id)
            self._ensure_not_started_for_file_changes(execution)

            file_names = request_item.files or []
            if not file_names:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No files provided for execution {execution_key}.",
                )
            if len(file_names) > 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Execution {execution_key} supports max 2 files "
                        "(input + questions) per request."
                    ),
                )

            used_types: set[str] = set()
            file_results: list[dict[str, Any]] = []
            for original_file_name in file_names:
                safe_file_name = self._validate_file_name_for_signed_url(original_file_name, "File")
                file_type = self._infer_file_type(safe_file_name, used_types)
                used_types.add(file_type)

                prefixed_name = f"{file_type}_{safe_file_name}"
                file_path = self.storage_service.build_execution_file_path(
                    user_id=user_id,
                    execution_id=str(execution.id),
                    file_name=prefixed_name,
                )

                self._set_file_path_by_type(execution, file_type, file_path)
                self._update_file_checkpoint(
                    execution,
                    file_type=file_type,
                    uploaded=False,
                    validated=False,
                    rows_detected=0,
                    columns_detected=[],
                    message=None,
                    missing_columns=[],
                )

                signed_upload = await self.storage_service.generate_upload_url(
                    file_path=file_path,
                    content_type="text/csv",
                    expiration=settings.SIGNED_UPLOAD_URL_EXPIRY_SECONDS,
                )
                signed_download = await self.storage_service.generate_download_url(
                    file_path=file_path,
                    expiration=settings.SIGNED_DOWNLOAD_URL_EXPIRY_SECONDS,
                )

                normalized_path = file_path.lstrip("/")
                file_results.append(
                    {
                        "file": normalized_path,
                        "url": signed_upload["url"],
                        "downloadableUrl": signed_download["url"],
                        "payload": {
                            "sourcePath": normalized_path,
                            "fileType": file_type,
                        },
                        "cloudStorage": (settings.CLOUD_STORAGE or settings.STORAGE_TYPE or "GCP").upper(),
                    }
                )

            execution.status = "draft"
            execution.failure_reason = None
            self.db.commit()
            self.db.refresh(execution)

            result[str(execution_key)] = {"files": file_results}

        return CloudSignedUrlResponse(
            responseCode="OK",
            message="Signed Url Generated Successfully.",
            result=result,
            meta={},
        )

    async def get_file_upload_url(
        self,
        execution_id: UUID,
        file_type: str,
        request_data: FileUploadUrlRequest,
        user_id: str,
    ) -> ExecutionFileUploadUrlResponse:
        """Step 2: create signed upload URL for one file section."""
        normalized_file_type = (file_type or "").strip().lower()
        if normalized_file_type not in {"input", "questions"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_type must be one of: input, questions",
            )

        execution = self._get_execution_or_404(execution_id, user_id)
        self._ensure_not_started_for_file_changes(execution)

        label = "Input file" if normalized_file_type == "input" else "Questions file"
        safe_file_name, normalized_content_type = self._validate_file_descriptor(
            request_data.file.file_name,
            request_data.file.size_bytes,
            request_data.file.content_type,
            label,
        )

        prefixed_name = f"{normalized_file_type}_{safe_file_name}"
        file_path = self.storage_service.build_execution_file_path(
            user_id=user_id,
            execution_id=str(execution.id),
            file_name=prefixed_name,
        )
        self._set_file_path_by_type(execution, normalized_file_type, file_path)
        self._set_file_size_by_type(execution, normalized_file_type, int(request_data.file.size_bytes))
        self._update_file_checkpoint(
            execution,
            file_type=normalized_file_type,
            uploaded=False,
            validated=False,
            rows_detected=0,
            columns_detected=[],
            message=None,
            missing_columns=[],
        )
        execution.status = "draft"
        self.db.commit()
        self.db.refresh(execution)

        signed_upload = await self.storage_service.generate_upload_url(
            file_path=file_path,
            content_type=normalized_content_type,
            expiration=settings.SIGNED_UPLOAD_URL_EXPIRY_SECONDS,
        )
        return ExecutionFileUploadUrlResponse(
            execution_id=execution.id,
            file_type=normalized_file_type,
            upload=SignedUrlPayload(**signed_upload),
        )

    async def complete_file_upload(
        self,
        execution_id: UUID,
        file_type: str,
        user_id: str,
    ) -> ExecutionFileCompleteResponse:
        """Step 2: confirm upload, detect rows/columns and persist preview metadata."""
        normalized_file_type = (file_type or "").strip().lower()
        if normalized_file_type not in {"input", "questions"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_type must be one of: input, questions",
            )

        execution = self._get_execution_or_404(execution_id, user_id)
        self._ensure_not_started_for_file_changes(execution)
        file_path = self._get_file_path_by_type(execution, normalized_file_type)
        if not file_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{normalized_file_type} file path is missing. Request a new upload URL first.",
            )

        metadata = await self.storage_service.get_file_metadata(file_path)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{normalized_file_type} file upload not found",
            )

        label = "Input file" if normalized_file_type == "input" else "Questions file"
        self._validate_uploaded_metadata(metadata, label)

        file_bytes = await self.storage_service.download_file(file_path)
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{normalized_file_type} file could not be read for metadata detection.",
            )

        headers, row_count = self._extract_headers_and_row_count(file_bytes, label)
        self._set_file_size_by_type(execution, normalized_file_type, int(metadata.get("size_bytes", 0)))
        self._update_file_checkpoint(
            execution,
            file_type=normalized_file_type,
            uploaded=True,
            validated=False,
            rows_detected=row_count,
            columns_detected=headers,
            message="File uploaded",
            missing_columns=[],
        )
        execution.status = "draft"
        execution.failure_reason = None
        self.db.commit()
        self.db.refresh(execution)

        return ExecutionFileCompleteResponse(
            execution_id=execution.id,
            file_type=normalized_file_type,
            uploaded=True,
            rows_detected=row_count,
            columns_detected=headers,
        )

    async def upload_file_direct(
        self,
        execution_id: UUID,
        file_type: str,
        file_name: str,
        content_type: Optional[str],
        file_bytes: bytes,
        user_id: str,
    ) -> ExecutionFileCompleteResponse:
        """Direct upload through backend (fallback when browser-to-cloud CORS fails)."""
        normalized_file_type = (file_type or "").strip().lower()
        if normalized_file_type not in {"input", "questions"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_type must be one of: input, questions",
            )

        execution = self._get_execution_or_404(execution_id, user_id)
        self._ensure_not_started_for_file_changes(execution)

        label = "Input file" if normalized_file_type == "input" else "Questions file"
        safe_file_name, normalized_content_type = self._validate_file_descriptor(
            file_name,
            len(file_bytes),
            content_type,
            label,
        )

        # Build file path and upload to storage
        prefixed_name = f"{normalized_file_type}_{safe_file_name}"
        file_path = self.storage_service.build_execution_file_path(
            user_id=user_id,
            execution_id=str(execution.id),
            file_name=prefixed_name,
        )

        # Upload file to storage
        await self.storage_service.upload_file(
            file_content=file_bytes,
            file_path=file_path,
            content_type=normalized_content_type,
        )

        # Extract headers and row count
        headers, row_count = self._extract_headers_and_row_count(file_bytes, label)

        # Update execution with file path and metadata
        self._set_file_path_by_type(execution, normalized_file_type, file_path)
        self._set_file_size_by_type(execution, normalized_file_type, len(file_bytes))
        self._update_file_checkpoint(
            execution,
            file_type=normalized_file_type,
            uploaded=True,
            validated=False,
            rows_detected=row_count,
            columns_detected=headers,
            message="File uploaded",
            missing_columns=[],
        )
        execution.status = "draft"
        execution.failure_reason = None
        self.db.commit()
        self.db.refresh(execution)

        return ExecutionFileCompleteResponse(
            execution_id=execution.id,
            file_type=normalized_file_type,
            uploaded=True,
            rows_detected=row_count,
            columns_detected=headers,
        )

    async def validate_execution_files(self, execution_id: UUID, user_id: str) -> ExecutionValidationResponse:
        """Step 3: validate both uploaded CSV files against source-type rules."""
        execution = self._get_execution_or_404(execution_id, user_id)
        self._ensure_not_started_for_file_changes(execution)
        source_type = self._get_csv_source_type(
            tenant_code=execution.tenant_code,
            organization_code=execution.organization_code,
            type_key=execution.csv_type_id or "",
        )
        if not source_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV source type configuration not found or inactive.",
            )

        input_result = FileValidationResult(file_type="input", valid=False)
        questions_result = FileValidationResult(file_type="questions", valid=False)

        input_path = execution.input_file_url
        questions_path = execution.questions_file_url
        evidence_context_config = source_type.evidence_context_config or {}
        title_column = str(evidence_context_config.get("title_column", "")).strip()
        input_tasks: set[str] = set()
        questions_tasks: set[str] = set()

        if not input_path:
            input_result.message = "Input file is missing. Please upload it and try again."
        if not questions_path:
            questions_result.message = "Questions file is missing. Please upload it and try again."

        if input_path:
            try:
                input_bytes = await self.storage_service.download_file(input_path)
                if not input_bytes:
                    raise HTTPException(status_code=400, detail="Input file could not be downloaded.")
                headers, row_count, preview_rows, input_tasks = self._parse_csv_preview(
                    input_bytes,
                    "Input file",
                    tracked_column=title_column,
                )
                input_result.rows_detected = row_count
                input_result.columns_detected = headers
                input_result.preview_rows = preview_rows
                self._validate_input_csv_metadata(headers, row_count, source_type)
                input_result.valid = True
                input_result.message = "Input file looks good."
                input_result.missing_columns = []
            except HTTPException as exc:
                detail = str(exc.detail)
                input_result.message = self._to_user_friendly_validation_message(detail, "Input file")
                if detail.startswith("Input file is missing required columns:"):
                    input_result.missing_columns = self._extract_missing_columns_from_detail(detail)

        if questions_path:
            try:
                questions_bytes = await self.storage_service.download_file(questions_path)
                if not questions_bytes:
                    raise HTTPException(status_code=400, detail="Questions file could not be downloaded.")
                headers, row_count, preview_rows, questions_tasks = self._parse_csv_preview(
                    questions_bytes,
                    "Questions file",
                    tracked_column=title_column,
                )
                questions_result.rows_detected = row_count
                questions_result.columns_detected = headers
                questions_result.preview_rows = preview_rows
                self._validate_questions_csv_metadata(headers, source_type)
                questions_result.valid = True
                questions_result.message = "Criteria file looks good."
                questions_result.missing_columns = []
            except HTTPException as exc:
                detail = str(exc.detail)
                questions_result.message = self._to_user_friendly_validation_message(detail, "Questions file")
                if detail.startswith("Questions file is missing mandatory columns:"):
                    questions_result.missing_columns = self._extract_missing_columns_from_detail(detail)
        
        # Cross-validate: Check if tasks in questions exist in input
        if input_result.valid and questions_result.valid and input_path and questions_path and title_column:
            try:
                self._validate_tasks_cross_reference_from_values(input_tasks, questions_tasks)
            except HTTPException as exc:
                # Mark questions as invalid if cross-validation fails
                questions_result.valid = False
                questions_result.message = self._to_user_friendly_validation_message(str(exc.detail), "Questions file")

        self._update_file_checkpoint(
            execution,
            file_type="input",
            validated=input_result.valid,
            message=input_result.message,
            missing_columns=input_result.missing_columns,
        )
        self._update_file_checkpoint(
            execution,
            file_type="questions",
            validated=questions_result.valid,
            message=questions_result.message,
            missing_columns=questions_result.missing_columns,
        )

        is_valid = input_result.valid and questions_result.valid
        execution.status = "validated" if is_valid else "draft"
        execution.failure_reason = None if is_valid else "File validation failed. Upload valid files and retry."
        self.db.commit()
        self.db.refresh(execution)

        return ExecutionValidationResponse(
            execution_id=execution.id,
            is_valid=is_valid,
            input_file=input_result,
            questions_file=questions_result,
        )

    async def start_execution(self, execution_id: UUID, user_id: str) -> ExecutionResponse:
        """Step 4: start analysis only after file validation success."""
        execution = self._get_execution_or_404(execution_id, user_id)

        checkpoint = self._checkpoint(execution)
        input_valid = bool(checkpoint["files"]["input"].get("validated"))
        questions_valid = bool(checkpoint["files"]["questions"].get("validated"))
        if not (input_valid and questions_valid):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Files are not validated. Upload valid files and run validation before starting analysis.",
            )

        if execution.status == "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Execution is already running",
            )
        if execution.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Execution is already completed.",
            )

        execution.status = "queued"
        execution.upload_completed_at = datetime.utcnow()
        execution.failure_reason = None
        self.db.commit()
        self.db.refresh(execution)

        self.worker.submit_job(execution.id)
        return self._to_execution_response(execution)

    async def init_execution_upload(
        self,
        request_data: ExecutionUploadInitRequest,
        current_user: UserResponse,
    ) -> ExecutionUploadInitResponse:
        """Create execution and return short-lived signed upload URLs."""
        input_file_name, input_content_type = self._validate_file_descriptor(
            request_data.input_file.file_name,
            request_data.input_file.size_bytes,
            request_data.input_file.content_type,
            "Input file",
        )
        questions_file_name, questions_content_type = self._validate_file_descriptor(
            request_data.questions_file.file_name,
            request_data.questions_file.size_bytes,
            request_data.questions_file.content_type,
            "Questions file",
        )

        tenant_code, organization_code = self._resolve_scope(current_user)

        source_type = self._get_csv_source_type(
            tenant_code=tenant_code,
            organization_code=organization_code,
            type_key=request_data.csv_type_id,
        )
        if not source_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or inactive csv_type_id for this tenant/organization.",
            )
        self._validate_scope_metadata(request_data, source_type)

        execution = Execution(
            tenant_code=tenant_code,
            organization_code=organization_code,
            name=request_data.name,
            csv_type_id=source_type.type_key,
            ai_model_id=request_data.ai_model_id or "gemini-2.5-flash",
            program_ref_id=request_data.program_ref_id,
            program_name=request_data.program_name,
            state=request_data.state,
            district=request_data.district,
            criterias_mode=request_data.criterias_mode,
            threshold_config=request_data.threshold_config,
            status="draft",
            created_by=current_user.id,
            input_file_size=request_data.input_file.size_bytes,
            questions_file_size=request_data.questions_file.size_bytes,
        )

        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        try:
            input_file_path = self.storage_service.build_execution_file_path(
                user_id=current_user.id,
                execution_id=str(execution.id),
                file_name=f"input_{input_file_name}",
            )
            questions_file_path = self.storage_service.build_execution_file_path(
                user_id=current_user.id,
                execution_id=str(execution.id),
                file_name=f"questions_{questions_file_name}",
            )

            execution.input_file_url = input_file_path
            execution.questions_file_url = questions_file_path
            self.db.commit()
            self.db.refresh(execution)

            upload_expiry = settings.SIGNED_UPLOAD_URL_EXPIRY_SECONDS
            input_upload = await self.storage_service.generate_upload_url(
                file_path=input_file_path,
                content_type=input_content_type,
                expiration=upload_expiry,
            )
            questions_upload = await self.storage_service.generate_upload_url(
                file_path=questions_file_path,
                content_type=questions_content_type,
                expiration=upload_expiry,
            )

            return ExecutionUploadInitResponse(
                execution_id=execution.id,
                status=execution.status,
                input_upload=SignedUrlPayload(**input_upload),
                questions_upload=SignedUrlPayload(**questions_upload),
            )

        except HTTPException:
            raise
        except Exception as exc:
            execution.status = "failed"
            execution.failure_reason = f"Upload initialization failed: {exc}"
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize upload: {exc}",
            )

    async def complete_execution_upload(self, execution_id: UUID, user_id: str) -> ExecutionResponse:
        """Validate uploaded files and queue the execution for processing."""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id,
        ).first()

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found",
            )

        if execution.status == "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Execution is already running",
            )

        if execution.upload_completed_at is not None:
            return self._to_execution_response(execution)

        if not execution.input_file_url or not execution.questions_file_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Execution file paths are missing",
            )

        input_metadata = await self.storage_service.get_file_metadata(execution.input_file_url)
        if not input_metadata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Input file upload not found",
            )
        self._validate_uploaded_metadata(input_metadata, "Input file")

        questions_metadata = await self.storage_service.get_file_metadata(execution.questions_file_url)
        if not questions_metadata:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Questions file upload not found",
            )
        self._validate_uploaded_metadata(questions_metadata, "Questions file")

        source_type = self._get_csv_source_type(
            tenant_code=execution.tenant_code,
            organization_code=execution.organization_code,
            type_key=execution.csv_type_id or "",
        )
        if not source_type:
            failure_reason = "CSV source type configuration not found or inactive."
            self._mark_execution_failed(execution, failure_reason)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=failure_reason,
            )

        try:
            input_file_bytes = await self.storage_service.download_file(execution.input_file_url)
            if not input_file_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Input file could not be read for validation.",
                )
            self._validate_input_csv_against_source(input_file_bytes, source_type)

            questions_file_bytes = await self.storage_service.download_file(execution.questions_file_url)
            if not questions_file_bytes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Questions file could not be read for validation.",
                )
            self._validate_questions_csv_against_source(questions_file_bytes, source_type)
        except HTTPException as exc:
            self._mark_execution_failed(execution, str(exc.detail))
            raise
        except Exception as exc:
            failure_reason = f"CSV validation failed: {exc}"
            self._mark_execution_failed(execution, failure_reason)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=failure_reason,
            ) from exc

        execution.input_file_size = int(input_metadata.get("size_bytes", execution.input_file_size or 0))
        execution.questions_file_size = int(questions_metadata.get("size_bytes", execution.questions_file_size or 0))
        execution.status = "queued"
        execution.upload_completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(execution)

        self.worker.submit_job(execution.id)
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

    def update_execution(
        self,
        execution_id: UUID,
        update_data: dict,
        user_id: str
    ) -> ExecutionResponse:
        """Update an execution (draft and validated executions can be updated)."""
        execution = self.db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.created_by == user_id
        ).first()

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found"
            )

        if execution.status not in {'draft', 'validated'}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft or validated executions can be updated"
            )

        # Update allowed fields
        allowed_fields = [
            'name', 'state', 'district', 'program_ref_id', 'program_name',
            'criterias_mode', 'threshold_config'
        ]
        
        for field, value in update_data.items():
            if field in allowed_fields and value is not None:
                setattr(execution, field, value)
        
        execution.updated_by = user_id
        
        try:
            self.db.commit()
            self.db.refresh(execution)
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.exception("Failed to update execution")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update execution"
            ) from exc

        return self._to_execution_response(execution)

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
