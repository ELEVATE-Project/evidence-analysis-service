"""
Celery application configuration for execution processing queue.
"""
from celery import Celery
from kombu import Exchange, Queue

from core.config import settings

execution_exchange = Exchange(
    name=settings.CELERY_TASK_QUEUE,
    type="direct",
    durable=True,
)

celery_app = Celery("evidence_analysis")
celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_default_queue=settings.CELERY_TASK_QUEUE,
    task_default_exchange=settings.CELERY_TASK_QUEUE,
    task_default_exchange_type="direct",
    task_default_routing_key=settings.CELERY_TASK_ROUTING_KEY,
    task_queues=(
        Queue(
            name=settings.CELERY_TASK_QUEUE,
            exchange=execution_exchange,
            routing_key=settings.CELERY_TASK_ROUTING_KEY,
            durable=True,
        ),
    ),
    task_create_missing_queues=False,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    worker_pool=settings.CELERY_WORKER_POOL,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

