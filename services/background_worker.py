"""
Background Worker
Queue submission wrapper for Celery-based execution processing.
"""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID
import logging
import traceback
import time

from core.config import settings

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Queue submission adapter used by API service."""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_JOBS)
        self._celery_available = False
        self._celery_app = None
        self._execution_task_name = None
        self._celery_retry_cooldown_seconds = 30
        self._celery_disabled_until_monotonic = 0.0

        try:
            from services.celery_app import celery_app  # Lazy optional import
            from services.execution_tasks import EXECUTION_TASK_NAME  # Lazy optional import

            self._celery_app = celery_app
            self._execution_task_name = EXECUTION_TASK_NAME
            self._celery_available = True
        except ModuleNotFoundError as exc:
            logger.warning(
                "Celery dependencies unavailable (%s). Falling back to local thread execution.",
                exc,
            )

        logger.info(
            "Background worker initialized (celery_enabled=%s, max_workers=%s)",
            self._celery_available,
            settings.MAX_CONCURRENT_JOBS,
        )

    def submit_job(self, execution_id: UUID):
        """
        Submit execution processing task to durable queue.
        """
        can_use_celery = (
            self._celery_available
            and self._celery_app
            and self._execution_task_name
            and time.monotonic() >= self._celery_disabled_until_monotonic
        )
        if can_use_celery:
            try:
                task_result = self._celery_app.send_task(
                    self._execution_task_name,
                    args=[str(execution_id)],
                    queue=settings.CELERY_TASK_QUEUE,
                    routing_key=settings.CELERY_TASK_ROUTING_KEY,
                )
                logger.info(
                    "Queued execution %s (task_id=%s)",
                    execution_id,
                    task_result.id,
                )
                return task_result.id
            except Exception as exc:  # noqa: BLE001
                self._celery_disabled_until_monotonic = (
                    time.monotonic() + self._celery_retry_cooldown_seconds
                )
                logger.warning(
                    "Celery enqueue unavailable for execution %s (%s). "
                    "Falling back to local thread execution for %ss.",
                    execution_id,
                    exc,
                    self._celery_retry_cooldown_seconds,
                )
                logger.debug("Celery enqueue failure details", exc_info=True)
        elif self._celery_available:
            remaining = max(
                0,
                int(self._celery_disabled_until_monotonic - time.monotonic()),
            )
            logger.info(
                "Skipping Celery enqueue for execution %s during cooldown (%ss remaining); "
                "using local thread fallback.",
                execution_id,
                remaining,
            )

        logger.info("Queueing execution %s via local thread fallback", execution_id)
        self.executor.submit(self._run_local_job, str(execution_id))
        return f"local-{execution_id}"

    @staticmethod
    def _run_local_job(execution_id: str):
        try:
            from services.execution_processor import (
                ExecutionProcessingError,
                ExecutionSkipError,
                mark_execution_failed,
                process_execution,
            )

            process_execution(execution_id)
        except ExecutionSkipError:
            logger.info("Local fallback skipped execution %s", execution_id)
        except ExecutionProcessingError as exc:
            logger.exception("Local fallback execution failed for %s", execution_id)
            try:
                mark_execution_failed(
                    execution_id,
                    retry_count=settings.CELERY_MAX_RETRIES,
                    reason=exc.message,
                    error_logs=exc.error_logs,
                )
            except Exception:
                logger.exception("Could not mark execution %s as failed", execution_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Local fallback execution failed for %s", execution_id)
            try:
                from services.execution_processor import mark_execution_failed

                mark_execution_failed(
                    execution_id,
                    retry_count=settings.CELERY_MAX_RETRIES,
                    reason=str(exc),
                    error_logs=traceback.format_exc(),
                )
            except Exception:
                logger.exception("Could not mark execution %s as failed", execution_id)

    def shutdown(self):
        """Shutdown local fallback pool."""
        logger.info("Shutting down background worker...")
        self.executor.shutdown(wait=True)
        logger.info("Background worker shutdown complete")
