"""
Background Worker
Creation-only phase: background processing is intentionally deferred.
"""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID
import logging

from core.config import settings

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Background worker stub for creation-only flow."""

    def __init__(self):
        # Keep executor initialization for compatibility with app lifespan/shutdown.
        self.executor = ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_JOBS)
        logger.info(
            "Background worker initialized in creation-only mode with %s workers",
            settings.MAX_CONCURRENT_JOBS,
        )

    def submit_job(self, execution_id: UUID):
        """
        Queue submission is intentionally a no-op until processing integration is implemented.
        Executions remain in queued state after start.
        """
        logger.info(
            "Processing deferred (creation-only mode); execution remains queued: %s",
            execution_id,
        )

    def shutdown(self):
        """Shutdown worker pool gracefully."""
        logger.info("Shutting down background worker...")
        self.executor.shutdown(wait=True)
