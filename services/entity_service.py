"""
Entity Service
Business logic layer for entity endpoints.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from clients.entity_management_client import (
    EntityManagementClient,
    EntityManagementClientConfig,
    EntityManagementClientError,
)
from core.config import settings

logger = logging.getLogger(__name__)


class EntityServiceError(Exception):
    """Structured service-layer exception for entity APIs."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details


class EntityService:
    """Service for fetching and caching entity data."""

    def __init__(
        self,
        client: EntityManagementClient,
        *,
        states_cache_enabled: bool,
        states_cache_ttl_seconds: int,
    ) -> None:
        self.client = client
        self.states_cache_enabled = states_cache_enabled
        self.states_cache_ttl_seconds = max(0, states_cache_ttl_seconds)

        self._states_cache: list[dict[str, Any]] = []
        self._states_cache_expiry: float = 0.0
        self._cache_lock = asyncio.Lock()

    @classmethod
    def from_settings(cls) -> "EntityService":
        """Build service instance from environment-backed settings."""
        config = EntityManagementClientConfig(
            base_url=settings.ENTITY_MGMT_BASE_URL,
            tenant_id=settings.ENTITY_MGMT_TENANT_ID,
            origin=settings.ENTITY_MGMT_ORIGIN,
            timeout_seconds=settings.ENTITY_MGMT_TIMEOUT_SECONDS,
            retry_attempts=settings.ENTITY_MGMT_RETRY_ATTEMPTS,
            retry_backoff_seconds=settings.ENTITY_MGMT_RETRY_BACKOFF_SECONDS,
        )
        logger.info(
            "EntityService configured with base_url=%s tenant_id=%s origin=%s",
            config.base_url,
            config.tenant_id,
            config.origin,
        )

        return cls(
            EntityManagementClient(config),
            states_cache_enabled=settings.ENTITY_MGMT_CACHE_ENABLED,
            states_cache_ttl_seconds=settings.ENTITY_MGMT_STATES_CACHE_TTL_SECONDS,
        )

    async def list_states(self) -> dict[str, Any]:
        """
        Fetch states with optional cache.
        Graceful degradation: returns stale cache when upstream fails.
        """
        cached = await self._get_cached_states()
        if cached is not None:
            return {
                "items": cached,
                "from_cache": True,
                "stale_cache_used": False,
            }

        try:
            states = await self.client.get_states()
            await self._set_cache(states)
            return {
                "items": states,
                "from_cache": False,
                "stale_cache_used": False,
            }
        except EntityManagementClientError as exc:
            stale_cache = await self._get_stale_cache()
            if stale_cache is not None:
                logger.warning("Using stale states cache due to upstream failure: %s", exc.code)
                return {
                    "items": stale_cache,
                    "from_cache": True,
                    "stale_cache_used": True,
                }

            raise EntityServiceError(
                "Failed to fetch states.",
                code=exc.code,
                status_code=exc.status_code,
                details=exc.details,
            ) from exc

    async def list_districts(self, state_id: str) -> dict[str, Any]:
        """Fetch districts for a specific state."""
        normalized_state_id = state_id.strip()
        if not normalized_state_id:
            raise EntityServiceError(
                "stateId is required.",
                code="INVALID_STATE_ID",
                status_code=400,
                details="Query parameter stateId cannot be blank",
            )

        try:
            districts = await self.client.get_districts(normalized_state_id)
            return {
                "items": districts,
                "from_cache": False,
                "stale_cache_used": False,
            }
        except EntityManagementClientError as exc:
            raise EntityServiceError(
                "Failed to fetch districts.",
                code=exc.code,
                status_code=exc.status_code,
                details=exc.details,
            ) from exc

    async def _get_cached_states(self) -> list[dict[str, Any]] | None:
        """Return valid states cache when enabled and available."""
        if not self.states_cache_enabled:
            return None

        now = time.monotonic()
        async with self._cache_lock:
            if self._states_cache and now < self._states_cache_expiry:
                return list(self._states_cache)
        return None

    async def _get_stale_cache(self) -> list[dict[str, Any]] | None:
        """Return stale cache for graceful degradation when enabled."""
        if not self.states_cache_enabled:
            return None

        async with self._cache_lock:
            if self._states_cache:
                return list(self._states_cache)
        return None

    async def _set_cache(self, states: list[dict[str, Any]]) -> None:
        """Write states cache only when caching is enabled."""
        if not self.states_cache_enabled:
            return

        async with self._cache_lock:
            self._states_cache = list(states)
            self._states_cache_expiry = time.monotonic() + self.states_cache_ttl_seconds
