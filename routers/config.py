"""
Config Router
Provides generic configuration list APIs.
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from core.dependencies import ConfigServiceDep
from models.entity_schemas import ErrorDetails, StandardAPIResponse
from models.schemas import UserResponse
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
    type: Literal["project"] = Query(...),
):
    """List config values by type. Current support: type=project."""
    try:
        items = config_service.list(type, current_user)
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
