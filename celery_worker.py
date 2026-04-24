"""
Celery worker entrypoint.

Run:
    celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2
"""
from services.celery_app import celery_app

# Ensure task registration side effects.
from services import execution_tasks as _execution_tasks  # noqa: F401

