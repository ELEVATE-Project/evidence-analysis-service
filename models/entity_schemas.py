"""
Schemas for Entity APIs.
"""
from typing import Any, Optional

from pydantic import BaseModel


class ErrorDetails(BaseModel):
    """Standardized error envelope."""

    code: str
    details: Optional[Any] = None


class StandardAPIResponse(BaseModel):
    """Standardized response envelope for entity endpoints."""

    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[ErrorDetails] = None
    meta: Optional[dict[str, Any]] = None

