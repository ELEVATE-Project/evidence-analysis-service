"""
Config Router
Provides generic configuration list APIs.
"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, Path, Query
from fastapi.responses import JSONResponse

from core.dependencies import ConfigServiceDep
from models.entity_schemas import ErrorDetails, StandardAPIResponse
from models.schemas import CsvSourceTypeUpdateRequest, ReportDownloadResponse, UserResponse
from services.auth_service import AuthService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/list",
    response_model=StandardAPIResponse,
    responses={
        400: {"model": StandardAPIResponse, "description": "Invalid config type"},
        401: {"model": StandardAPIResponse, "description": "Unauthorized"},
        500: {"model": StandardAPIResponse, "description": "Unexpected internal error"},
    },
)
async def list(
    config_service: ConfigServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    type: Literal["csv_source_type", "evidence_type", "school_filter"] = Query(...),
    type_key: Optional[str] = Query(
        default=None,
        description="CsvSourceType.type_key to scope evidence_type/school_filter to "
        "(e.g. a value from a type=csv_source_type item). Ignored for type=csv_source_type "
        "itself. Required for type=evidence_type and type=school_filter — a request for "
        "either without type_key returns 400 rather than silently resolving to 'project_report'.",
    ),
):
    """List config values by type. Supported: type=csv_source_type, type=evidence_type, type=school_filter."""
    try:
        items = config_service.list(type, current_user, type_key=type_key)
        payload = StandardAPIResponse(
            success=True,
            message="Config fetched successfully" if items else "No config found",
            data=items,
            meta={"type": type, "count": len(items)},
        )
        return JSONResponse(status_code=200, content=payload.model_dump(exclude_none=True))
    except Exception as exc:
        status_code = getattr(exc, "status_code", 500)
        detail = getattr(exc, "detail", "Unexpected internal error")
        if status_code >= 500:
            logger.exception("Unexpected error while fetching config")
        else:
            logger.warning("Config list request failed: %s", detail)
        code = "INVALID_CONFIG_TYPE" if status_code == 400 else "INTERNAL_ERROR"
        payload = StandardAPIResponse(
            success=False,
            message="Failed to fetch config",
            error=ErrorDetails(code=code, details=detail),
        )
        return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


@router.get(
    "/csv-source-types/{type_key}/sample/{file_type}",
    response_model=ReportDownloadResponse,
    responses={
        400: {"model": StandardAPIResponse, "description": "Invalid file_type parameter"},
        404: {"model": StandardAPIResponse, "description": "Sample file not found"},
        401: {"model": StandardAPIResponse, "description": "Unauthorized"},
        500: {"model": StandardAPIResponse, "description": "Failed to generate download URL"},
    },
)
async def get_sample_csv_url(
    config_service: ConfigServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    type_key: str = Path(..., description="CsvSourceType.type_key, e.g. 'project_report'"),
    file_type: Literal["input", "criteria", "school_filter"] = Path(..., description="Sample file type"),
):
    """
    Get signed download URL for sample CSV file.

    Args:
        type_key: CsvSourceType.type_key — the same identifier execution.csv_type_id uses
        file_type: One of 'input', 'criteria', or 'school_filter'

    Returns:
        Signed download URL with expiration time
    """
    return await config_service.get_sample_file_url(type_key, file_type, current_user)


@router.patch(
    "/csv-source-types/{type_key}",
    response_model=StandardAPIResponse,
    responses={
        400: {"model": StandardAPIResponse, "description": "No fields provided to update"},
        401: {"model": StandardAPIResponse, "description": "Unauthorized"},
        403: {"model": StandardAPIResponse, "description": "Invalid or missing internal access token"},
        404: {"model": StandardAPIResponse, "description": "CSV source type not found"},
        422: {"model": StandardAPIResponse, "description": "A required field was set to null"},
        500: {"model": StandardAPIResponse, "description": "Failed to update CSV source type"},
    },
)
async def update_csv_source_type(
    request: CsvSourceTypeUpdateRequest,
    config_service: ConfigServiceDep,
    current_user: UserResponse = Depends(AuthService.get_current_user),
    type_key: str = Path(..., description="CsvSourceType.type_key, e.g. 'project_report'"),
    x_internal_access_token: str = Header(default="", alias="X-Internal-Access-Token"),
):
    """
    Partial update of a CsvSourceType row, scoped to the caller's own tenant/
    organization. Requires a valid JWT (for tenant/org scoping and the updated_by
    audit trail) plus the X-Internal-Access-Token header matching
    settings.INTERNAL_ACCESS_TOKEN. Only fields present in the request body are
    changed — e.g. {"sample_criteria_file_url": null} clears just that field, which
    forces the next application startup to re-upload the sample criteria CSV from
    the current repo file instead of skipping it (see services/bootstrap.py).
    """
    try:
        AuthService.verify_internal_access_token(x_internal_access_token)
        result = config_service.update_csv_source_type(type_key, request, current_user)
        payload = StandardAPIResponse(
            success=True,
            message="CSV source type updated successfully",
            data=result,
        )
        return JSONResponse(status_code=200, content=payload.model_dump(exclude_none=True))
    except Exception as exc:
        status_code = getattr(exc, "status_code", 500)
        detail = getattr(exc, "detail", "Unexpected internal error")
        if status_code >= 500:
            logger.exception("Unexpected error while updating CSV source type")
        else:
            logger.warning("CSV source type update request failed: %s", detail)
        code = {
            400: "NO_FIELDS_PROVIDED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            422: "REQUIRED_FIELD_EMPTY",
        }.get(status_code, "INTERNAL_ERROR")
        payload = StandardAPIResponse(
            success=False,
            message="Failed to update CSV source type",
            error=ErrorDetails(code=code, details=detail),
        )
        return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))
