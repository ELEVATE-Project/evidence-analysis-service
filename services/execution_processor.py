"""
Execution processor
Runs end-to-end execution pipeline in an isolated workspace.
"""
from __future__ import annotations

import asyncio
import csv
import os
import shutil
import socket
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.config import SERVICE_ROOT, settings
from db.database import SessionLocal
from models.csv_source_type import CsvSourceType
from models.execution import Execution
from services.gemini_runtime import build_gemini_env_overrides
from services.storage_service import StorageService


class ExecutionSkipError(Exception):
    """Raised when execution cannot be claimed or should not be processed."""


class ExecutionProcessingError(Exception):
    """Raised when execution processing fails and should be retried/failed."""

    def __init__(self, message: str, error_logs: str = ""):
        super().__init__(message)
        self.message = message
        self.error_logs = error_logs


@dataclass
class ExecutionWorkspace:
    root_dir: Path
    input_dir: Path
    preprocessor_output_dir: Path
    processor_input_dir: Path
    processor_output_dir: Path
    input_csv: Path
    questions_csv: Path
    preprocessed_csv: Path
    final_output_csv: Path
    checkpoint_file: Path
    api_usage_log_file: Path


def _run_async(coro):
    return asyncio.run(coro)


def _resolve_script_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (SERVICE_ROOT / candidate).resolve()
    if not candidate.exists():
        raise ExecutionProcessingError(f"Script not found: {candidate}")
    return candidate


def _count_csv_rows(file_path: Path) -> int:
    with file_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        next(reader, None)  # skip header
        return sum(1 for row in reader if any((cell or "").strip() for cell in row))


def _build_workspace(execution_id: UUID) -> ExecutionWorkspace:
    root_dir = Path(settings.EXECUTION_WORKSPACE_ROOT).resolve() / str(execution_id)
    input_dir = root_dir / "input"
    preprocessor_output_dir = root_dir / "preprocessor_output"
    processor_input_dir = root_dir / "processor_input"
    processor_output_dir = root_dir / "processor_output"

    input_dir.mkdir(parents=True, exist_ok=True)
    preprocessor_output_dir.mkdir(parents=True, exist_ok=True)
    processor_input_dir.mkdir(parents=True, exist_ok=True)
    processor_output_dir.mkdir(parents=True, exist_ok=True)

    return ExecutionWorkspace(
        root_dir=root_dir,
        input_dir=input_dir,
        preprocessor_output_dir=preprocessor_output_dir,
        processor_input_dir=processor_input_dir,
        processor_output_dir=processor_output_dir,
        input_csv=input_dir / "input.csv",
        questions_csv=input_dir / "question.csv",
        preprocessed_csv=preprocessor_output_dir / "preprocessed_data.csv",
        final_output_csv=processor_output_dir / "merged_output.csv",
        checkpoint_file=processor_output_dir / ".processing_checkpoint.json",
        api_usage_log_file=processor_output_dir / "api_usage_log.csv",
    )


def _resolve_processor_columns_from_config(db: Session, execution: Execution) -> dict[str, str]:
    columns: dict[str, str] = {}
    csv_type_id = (execution.csv_type_id or "").strip()
    if not csv_type_id:
        return columns

    source_type = (
        db.query(CsvSourceType)
        .filter(
            CsvSourceType.tenant_code == execution.tenant_code,
            CsvSourceType.organization_code == execution.organization_code,
            CsvSourceType.type_key == csv_type_id,
            CsvSourceType.is_active.is_(True),
        )
        .first()
    )
    if not source_type:
        return columns

    evidence_context_config = (
        source_type.evidence_context_config if isinstance(source_type.evidence_context_config, dict) else {}
    )
    title_column = str(evidence_context_config.get("title_column", "")).strip()
    if title_column:
        columns["task_column"] = title_column

    question_config = source_type.question_config if isinstance(source_type.question_config, dict) else {}
    question_text_column = str(question_config.get("question_column", "")).strip()
    if not question_text_column:
        mandatory_columns = question_config.get("mandatory_columns", [])
        if isinstance(mandatory_columns, list):
            for column in mandatory_columns:
                column_str = str(column or "").strip()
                if not column_str:
                    continue
                if column_str == "evidence_context_config.title_column":
                    continue
                question_text_column = column_str
                break

    if question_text_column:
        columns["question_text_column"] = question_text_column

    return columns


def _run_command(command: list[str], env: dict[str, str], label: str) -> None:
    result = subprocess.run(
        command,
        cwd=str(SERVICE_ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode == 0:
        return

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    combined_logs = f"{label} failed.\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}".strip()
    raise ExecutionProcessingError(
        message=f"{label} failed with exit code {result.returncode}",
        error_logs=combined_logs,
    )


def _inject_gemini_env(base_env: dict[str, str]) -> dict[str, str]:
    """
    Ensure processor subprocess receives Gemini auth/model env even when
    parent process loaded values via pydantic settings only.
    """
    env = dict(base_env)
    env.update(build_gemini_env_overrides(base_env))
    return env


def _claim_execution(
    db: Session,
    *,
    execution_id: UUID,
    worker_id: str,
) -> Execution:
    exists = db.query(Execution.id).filter(Execution.id == execution_id).first()
    if not exists:
        raise ExecutionSkipError(f"Execution not found: {execution_id}")

    execution = (
        db.query(Execution)
        .filter(Execution.id == execution_id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if execution is None:
        raise ExecutionSkipError(f"Execution is locked by another worker: {execution_id}")

    if (execution.status or "").strip().lower() != "queued":
        raise ExecutionSkipError(
            f"Execution is not queued (current status: {execution.status})"
        )

    execution.status = "in_progress"
    execution.worker_id = worker_id
    execution.processing_started_at = datetime.utcnow()
    execution.processing_completed_at = None
    execution.completed_at = None
    execution.failure_reason = None
    execution.error_logs = None
    db.commit()
    db.refresh(execution)
    return execution


def _mark_execution_completed(
    execution_id: UUID,
    *,
    output_file_url: str,
    output_file_size: int,
    processed_rows: int,
    elapsed_seconds: float,
) -> None:
    db = SessionLocal()
    try:
        execution = (
            db.query(Execution)
            .filter(Execution.id == execution_id)
            .with_for_update()
            .first()
        )
        if not execution:
            return

        completed_at = datetime.utcnow()
        execution.status = "completed"
        execution.output_file_url = output_file_url
        execution.output_file_size = output_file_size
        execution.processed_rows = processed_rows
        execution.total_rows = processed_rows
        execution.processing_completed_at = completed_at
        execution.completed_at = completed_at
        execution.failure_reason = None
        execution.error_logs = None
        if processed_rows > 0:
            execution.average_processing_time = elapsed_seconds / processed_rows
        db.commit()
    finally:
        db.close()


def mark_execution_for_retry(
    execution_id: str,
    *,
    retry_count: int,
    reason: str,
    error_logs: str,
) -> None:
    execution_uuid = UUID(str(execution_id))
    db = SessionLocal()
    try:
        execution = (
            db.query(Execution)
            .filter(Execution.id == execution_uuid)
            .with_for_update(skip_locked=True)
            .first()
        )
        if not execution:
            return

        execution.status = "queued"
        execution.retry_count = retry_count
        execution.failure_reason = reason
        execution.error_logs = error_logs
        db.commit()
    finally:
        db.close()


def mark_execution_failed(
    execution_id: str,
    *,
    retry_count: int,
    reason: str,
    error_logs: str,
) -> None:
    execution_uuid = UUID(str(execution_id))
    db = SessionLocal()
    try:
        execution = (
            db.query(Execution)
            .filter(Execution.id == execution_uuid)
            .with_for_update(skip_locked=True)
            .first()
        )
        if not execution:
            return

        failed_at = datetime.utcnow()
        execution.status = "failed"
        execution.retry_count = retry_count
        execution.failure_reason = reason
        execution.error_logs = error_logs
        execution.processing_completed_at = failed_at
        execution.completed_at = failed_at
        db.commit()
    finally:
        db.close()


def process_execution(execution_id: str) -> dict[str, Any]:
    execution_uuid = UUID(str(execution_id))
    worker_id = f"celery@{socket.gethostname()}:{os.getpid()}"
    workspace: ExecutionWorkspace | None = None
    start_ts = datetime.utcnow()

    db = SessionLocal()
    try:
        execution = _claim_execution(db, execution_id=execution_uuid, worker_id=worker_id)
        storage_service = StorageService()

        if not execution.input_file_url or not execution.criterias_file_url:
            raise ExecutionProcessingError(
                "Execution is missing input/questions file URLs."
            )

        workspace = _build_workspace(execution.id)

        input_bytes = _run_async(storage_service.download_file(execution.input_file_url))
        questions_bytes = _run_async(storage_service.download_file(execution.criterias_file_url))
        if not input_bytes:
            raise ExecutionProcessingError("Input file could not be downloaded from storage.")
        if not questions_bytes:
            raise ExecutionProcessingError("Questions file could not be downloaded from storage.")

        workspace.input_csv.write_bytes(input_bytes)
        workspace.questions_csv.write_bytes(questions_bytes)

        preprocessor_script = _resolve_script_path(settings.PREPROCESS_SCRIPT_PATH)
        processor_script = _resolve_script_path(settings.PROCESSOR_SCRIPT_PATH)

        base_env = _inject_gemini_env(os.environ.copy())
        preprocessor_env = {
            **base_env,
            "PYTHONUNBUFFERED": "1",
        }
        configured_columns = _resolve_processor_columns_from_config(db, execution)
        question_task_column = configured_columns.get("task_column", "")
        question_text_column = configured_columns.get("question_text_column", "")
        if question_task_column:
            preprocessor_env["PREPROCESS_QUESTION_TASK_COLUMN"] = question_task_column

        preprocessor_cmd = [
            sys.executable,
            str(preprocessor_script),
            "--input-csv",
            str(workspace.input_csv),
            "--question-csv",
            str(workspace.questions_csv),
            "--output-dir",
            str(workspace.preprocessor_output_dir),
            "--split-files",
            "no",
            "--use-school-filter",
            "false",
        ]
        _run_command(preprocessor_cmd, preprocessor_env, "Pre-processor script")

        if not workspace.preprocessed_csv.exists():
            raise ExecutionProcessingError(
                f"Pre-processed file not found: {workspace.preprocessed_csv}"
            )

        shutil.copy2(
            workspace.preprocessed_csv,
            workspace.processor_input_dir / "input.csv",
        )

        processor_env = {
            **base_env,
            "PYTHONUNBUFFERED": "1",
            "RESUME_FROM_CHECKPOINT": str(settings.PROCESSOR_RESUME_FROM_CHECKPOINT),
            "CHECKPOINT_CLEANUP_ON_SUCCESS": "True",
        }
        if question_task_column:
            processor_env["PROCESSOR_QUESTION_TASK_COLUMN"] = question_task_column
            processor_env["PROCESSOR_INPUT_TASK_COLUMN"] = question_task_column
        if question_text_column:
            processor_env["PROCESSOR_QUESTION_TEXT_COLUMN"] = question_text_column

        processor_cmd = [
            sys.executable,
            str(processor_script),
            "--input-dir",
            str(workspace.processor_input_dir),
            "--output-dir",
            str(workspace.processor_output_dir),
            "--final-output-file",
            str(workspace.final_output_csv),
            "--checkpoint-file",
            str(workspace.checkpoint_file),
            "--api-usage-log-file",
            str(workspace.api_usage_log_file),
            "--questions-file",
            str(workspace.questions_csv),
            "--max-processed-rows",
            str(settings.PROCESSOR_MAX_ROWS),
        ]
        _run_command(processor_cmd, processor_env, "Processor script")

        if not workspace.final_output_csv.exists():
            raise ExecutionProcessingError(
                f"Merged output file not found: {workspace.final_output_csv}"
            )

        output_bytes = workspace.final_output_csv.read_bytes()
        processed_rows = _count_csv_rows(workspace.final_output_csv)
        output_file_name = f"output_{execution.id}.csv"
        output_file_path = storage_service.build_execution_file_path(
            user_id=execution.created_by or "system",
            execution_id=str(execution.id),
            file_name=output_file_name,
        )
        uploaded_output_path = _run_async(
            storage_service.upload_file(
                file_content=output_bytes,
                file_path=output_file_path,
                content_type="text/csv",
            )
        )

        elapsed_seconds = (datetime.utcnow() - start_ts).total_seconds()
        _mark_execution_completed(
            execution.id,
            output_file_url=uploaded_output_path,
            output_file_size=len(output_bytes),
            processed_rows=processed_rows,
            elapsed_seconds=elapsed_seconds,
        )

        if settings.EXECUTION_CLEANUP_ON_SUCCESS and workspace.root_dir.exists():
            shutil.rmtree(workspace.root_dir, ignore_errors=True)

        return {
            "status": "completed",
            "execution_id": str(execution.id),
            "output_file_url": uploaded_output_path,
            "processed_rows": processed_rows,
            "worker_id": worker_id,
        }
    except ExecutionSkipError:
        raise
    except ExecutionProcessingError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ExecutionProcessingError(
            message=str(exc),
            error_logs=traceback.format_exc(),
        ) from exc
    finally:
        db.close()
