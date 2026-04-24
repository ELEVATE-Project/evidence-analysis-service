"""
Entities Router
Provides internal APIs for state and district lookups.
"""
import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from core.dependencies import EntityServiceDep
from models.entity_schemas import ErrorDetails, StandardAPIResponse
from services.entity_service import EntityServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


def _error_response(
    status_code: int,
    *,
    code: str,
    details: object | None = None,
    message: str = "Failed to fetch data",
) -> JSONResponse:
    payload = StandardAPIResponse(
        success=False,
        message=message,
        error=ErrorDetails(code=code, details=details),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(exclude_none=True),
    )


@router.get(
    "/states",
    response_model=StandardAPIResponse,
    responses={
        500: {"model": StandardAPIResponse, "description": "Unexpected internal error"},
    },
)
async def get_states(entity_service: EntityServiceDep):
    """Fetch all states from external Entity Management service."""
    try:
        result = await entity_service.list_states()
    except EntityServiceError as exc:
        logger.warning("Failed to fetch states: %s", exc.code)
        return _error_response(
            exc.status_code,
            code=exc.code,
            details=exc.details,
        )
    except Exception:
        logger.exception("Unexpected error while fetching states")
        return _error_response(
            500,
            code="INTERNAL_ERROR",
            details="Unexpected internal error",
        )

    items = result["items"]
    return StandardAPIResponse(
        success=True,
        message="States fetched successfully" if items else "No states found",
        data=items,
        meta={
            "count": len(items),
            "from_cache": result["from_cache"],
            "stale_cache_used": result["stale_cache_used"],
        },
    )


@router.get(
    "/districts",
    response_model=StandardAPIResponse,
    responses={
        400: {"model": StandardAPIResponse, "description": "Invalid stateId"},
        500: {"model": StandardAPIResponse, "description": "Unexpected internal error"},
    },
)
async def get_districts(
    entity_service: EntityServiceDep,
    state_id: str = Query(..., alias="stateId"),
):
    """Fetch districts for the given state ID."""
    try:
        result = await entity_service.list_districts(state_id)
    except EntityServiceError as exc:
        logger.warning("Failed to fetch districts for stateId=%s: %s", state_id, exc.code)
        return _error_response(
            exc.status_code,
            code=exc.code,
            details=exc.details,
        )
    except Exception:
        logger.exception("Unexpected error while fetching districts")
        return _error_response(
            500,
            code="INTERNAL_ERROR",
            details="Unexpected internal error",
        )

    items = result["items"]
    return StandardAPIResponse(
        success=True,
        message="Districts fetched successfully" if items else "No districts found",
        data=items,
        meta={
            "count": len(items),
            "stateId": state_id.strip(),
        },
    )
