"""
Reports Router
Handles report generation, viewing, and export
"""
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse

from core.dependencies import ReportServiceDep
from models.schemas import ReportResponse, UserResponse
from services.auth_service import AuthService

router = APIRouter()


@router.get("/{execution_id}", response_model=ReportResponse)
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


@router.get("/{execution_id}/download")
async def download_report(
    execution_id: UUID,
    report_service: ReportServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    format: str = Query("csv"),
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

    file_path = report_service.get_output_csv_path(execution_id, current_user.id)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found",
        )

    return FileResponse(
        file_path,
        media_type="text/csv",
        filename=f"execution_{execution_id}_output.csv",
    )


@router.get("/{execution_id}/html")
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
