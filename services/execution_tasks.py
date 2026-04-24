"""
Celery task definitions for execution processing.
"""
import logging

from core.config import settings
from services.celery_app import celery_app
from services.execution_processor import (
    ExecutionProcessingError,
    ExecutionSkipError,
    mark_execution_failed,
    mark_execution_for_retry,
    process_execution,
)

logger = logging.getLogger(__name__)

EXECUTION_TASK_NAME = "executions.process_execution"


@celery_app.task(
    bind=True,
    name=EXECUTION_TASK_NAME,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_execution_task(self, execution_id: str) -> dict:
    """Process one queued execution end-to-end."""
    try:
        return process_execution(execution_id)
    except ExecutionSkipError as exc:
        logger.info("Skipping execution %s: %s", execution_id, exc)
        return {"status": "skipped", "execution_id": execution_id, "reason": str(exc)}
    except ExecutionProcessingError as exc:
        next_retry = int(self.request.retries or 0) + 1
        if next_retry <= settings.CELERY_MAX_RETRIES:
            mark_execution_for_retry(
                execution_id,
                retry_count=next_retry,
                reason=f"Retry {next_retry}/{settings.CELERY_MAX_RETRIES}: {exc.message}",
                error_logs=exc.error_logs,
            )
            countdown = settings.CELERY_RETRY_BACKOFF_SECONDS * (2 ** (next_retry - 1))
            logger.warning(
                "Execution %s failed, scheduling retry %s/%s in %ss: %s",
                execution_id,
                next_retry,
                settings.CELERY_MAX_RETRIES,
                countdown,
                exc.message,
            )
            raise self.retry(exc=exc, countdown=countdown, max_retries=settings.CELERY_MAX_RETRIES)

        final_retry_count = int(self.request.retries or settings.CELERY_MAX_RETRIES)
        mark_execution_failed(
            execution_id,
            retry_count=final_retry_count,
            reason=exc.message,
            error_logs=exc.error_logs,
        )
        logger.exception(
            "Execution %s failed permanently after retries: %s",
            execution_id,
            exc.message,
        )
        return {
            "status": "failed",
            "execution_id": execution_id,
            "reason": exc.message,
        }

