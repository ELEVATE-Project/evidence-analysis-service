"""
Entity Management Client
Handles calls to external Entity Management APIs.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EntityManagementClientConfig:
    """Configuration for Entity Management API client."""

    base_url: str
    tenant_id: str
    origin: str
    timeout_seconds: float = 10.0
    retry_attempts: int = 2
    retry_backoff_seconds: float = 0.5


class EntityManagementClientError(Exception):
    """Structured exception for upstream Entity Management failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "ENTITY_CLIENT_ERROR",
        status_code: int = 502,
        details: Any = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details
        self.retryable = retryable


class EntityManagementClient:
    """External API client for states and districts."""

    def __init__(self, config: EntityManagementClientConfig) -> None:
        self.config = config
        self._base_url = config.base_url.strip().rstrip("/")
        # Support both styles:
        # 1) https://host
        # 2) https://host/entity-management
        if self._base_url.endswith("/entity-management"):
            self._entities_api_base_path = "/v1/entities"
        else:
            self._entities_api_base_path = "/entity-management/v1/entities"

    async def get_states(self) -> list[dict[str, Any]]:
        """Fetch state list from Entity Management service."""
        payload = await self._request(
            f"{self._entities_api_base_path}/entityListBasedOnEntityType",
            params={"entityType": "state"},
        )
        return self._extract_entities(payload, "states")

    async def get_districts(self, state_id: str) -> list[dict[str, Any]]:
        """Fetch district list for a state from Entity Management service."""
        payload = await self._request(
            f"{self._entities_api_base_path}/subEntityList/{state_id}",
            params={"type": "district"},
        )
        return self._extract_entities(payload, f"districts for state {state_id}")

    async def _request(self, path: str, *, params: dict[str, Any]) -> Any:
        """Execute GET requests with timeout and retry handling."""
        if not self._base_url:
            raise EntityManagementClientError(
                "Entity Management base URL is not configured.",
                code="CONFIG_ERROR",
                status_code=500,
                details="Set ENTITY_MGMT_BASE_URL in environment variables",
            )

        url = f"{self._base_url}{path}"
        max_retries = max(0, self.config.retry_attempts)
        max_attempts = max_retries + 1
        last_error: EntityManagementClientError | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.config.timeout_seconds,
                    headers={
                        "tenantid": self.config.tenant_id,
                        "origin": self.config.origin,
                    },
                ) as client:
                    response = await client.get(url, params=params)

                if response.status_code >= 500 and attempt < max_attempts:
                    wait_seconds = self.config.retry_backoff_seconds * attempt
                    logger.warning(
                        "Entity Management API returned %s, retrying in %.2fs",
                        response.status_code,
                        wait_seconds,
                    )
                    await asyncio.sleep(wait_seconds)
                    continue

                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as exc:
                    raise EntityManagementClientError(
                        "Entity Management API returned invalid JSON response.",
                        code="INVALID_RESPONSE",
                        status_code=502,
                        details=str(exc),
                    ) from exc

            except httpx.TimeoutException as exc:
                last_error = EntityManagementClientError(
                    "Entity Management request timed out.",
                    code="TIMEOUT_ERROR",
                    status_code=504,
                    details=str(exc),
                    retryable=True,
                )
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                error_details = {
                    "status_code": status_code,
                    "url": str(exc.request.url),
                }
                if status_code >= 500:
                    last_error = EntityManagementClientError(
                        "Entity Management service is currently unavailable.",
                        code="UPSTREAM_SERVER_ERROR",
                        status_code=502,
                        details=error_details,
                        retryable=True,
                    )
                else:
                    mapped_status = 400 if status_code in {400, 404} else 502
                    last_error = EntityManagementClientError(
                        "Entity Management service rejected the request.",
                        code="UPSTREAM_REQUEST_REJECTED",
                        status_code=mapped_status,
                        details=error_details,
                    )
                logger.warning(
                    "Entity Management HTTP error: status=%s url=%s",
                    status_code,
                    exc.request.url,
                )
            except httpx.RequestError as exc:
                last_error = EntityManagementClientError(
                    "Unable to connect to Entity Management service.",
                    code="NETWORK_ERROR",
                    status_code=503,
                    details=str(exc),
                    retryable=True,
                )

            if last_error and last_error.retryable and attempt < max_attempts:
                wait_seconds = self.config.retry_backoff_seconds * attempt
                logger.warning(
                    "Entity Management call failed (%s), retrying in %.2fs",
                    last_error.code,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)
                continue

            if last_error:
                raise last_error

        raise EntityManagementClientError(
            "Failed to call Entity Management service.",
            code="UNKNOWN_CLIENT_ERROR",
            status_code=502,
        )

    @staticmethod
    def _extract_entities(payload: Any, entity_name: str) -> list[dict[str, Any]]:
        """
        Normalize multiple possible upstream response shapes into a list of dicts.
        """
        candidates: list[Any] = []

        if isinstance(payload, list):
            candidates.append(payload)
        elif isinstance(payload, dict):
            keys = ("data", "result", "entities", "items", "list", "response")
            nested_keys = ("data", "entities", "items", "list", "results", "subEntities")

            candidates.extend(payload.get(key) for key in keys)

            for key in keys:
                nested = payload.get(key)
                if isinstance(nested, dict):
                    candidates.extend(nested.get(nested_key) for nested_key in nested_keys)
        else:
            raise EntityManagementClientError(
                f"Unexpected response type for {entity_name}.",
                code="INVALID_RESPONSE",
                status_code=502,
                details=f"type={type(payload).__name__}",
            )

        for candidate in candidates:
            if isinstance(candidate, list):
                normalized: list[dict[str, Any]] = []
                for item in candidate:
                    if isinstance(item, dict):
                        normalized.append(item)
                    else:
                        normalized.append({"value": item})
                return normalized

        raise EntityManagementClientError(
            f"Unexpected response format while parsing {entity_name}.",
            code="INVALID_RESPONSE",
            status_code=502,
        )
