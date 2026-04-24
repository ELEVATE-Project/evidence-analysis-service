"""
Reports Router
Handles report generation, viewing, and export
"""
import io
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse

from core.dependencies import ReportServiceDep
from models.schemas import HTTPErrorResponse, ReportDownloadResponse, ReportResponse, UserResponse
from services.auth_service import AuthService
from services.report_service import (
    ReportCsvConflictError,
    ReportCsvNotFoundError,
    ReportCsvValidationError,
)

router = APIRouter()


@router.get(
    "/{execution_id}",
    response_model=ReportResponse,
    responses={
        404: {"model": HTTPErrorResponse, "description": "Report not found or execution not completed"},
    },
)
async def get_report(
    execution_id: UUID,
    report_service: ReportServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """
    Get report data for a completed execution.
    Returns structured data for frontend rendering.
    """
    report = report_service.get_report(execution_id, current_user.id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found or execution not completed",
        )
    return report


@router.get(
    "/{execution_id}/download",
    response_model=ReportDownloadResponse,
    responses={
        400: {"model": HTTPErrorResponse, "description": "Unsupported report format"},
        404: {"model": HTTPErrorResponse, "description": "Report file not found"},
    },
)
async def download_report(
    execution_id: UUID,
    report_service: ReportServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    format: Literal["csv"] = Query("csv"),
):
    """
    Download report in specified format.
    Currently supports: csv
    """
    if format != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}",
        )

    signed_download = await report_service.get_output_download_url(execution_id, current_user.id)
    if not signed_download:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found",
        )

    return signed_download


@router.get(
    "/{execution_id}/csv",
    response_class=Response,
    responses={
        200: {
            "description": "Validated CSV content",
            "content": {
                "text/csv": {
                    "schema": {"type": "string"}
                }
            },
        },
        404: {"model": HTTPErrorResponse, "description": "Report output file not found"},
        409: {"model": HTTPErrorResponse, "description": "Execution not completed yet"},
        422: {"model": HTTPErrorResponse, "description": "Output CSV validation failed"},
    },
)
async def get_report_csv(
    execution_id: UUID,
    report_service: ReportServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """
    Download and validate the output CSV for report rendering.
    Returns CSV text when successful.
    """
    try:
        csv_content = await report_service.get_output_csv_content(execution_id, current_user.id)
    except ReportCsvNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ReportCsvConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ReportCsvValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return Response(content=csv_content, media_type="text/csv; charset=utf-8")


@router.get(
    "/{execution_id}/html",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Generated HTML report",
            "content": {
                "text/html": {
                    "schema": {"type": "string"}
                }
            },
        },
        404: {"model": HTTPErrorResponse, "description": "Report not found"},
    },
)
async def get_html_report(
    execution_id: UUID,
    report_service: ReportServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
):
    """Generate and return HTML report."""
    html_content = report_service.generate_html_report(execution_id, current_user.id)
    if not html_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return StreamingResponse(io.BytesIO(html_content.encode()), media_type="text/html")
