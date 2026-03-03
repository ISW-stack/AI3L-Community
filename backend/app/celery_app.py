from celery import Celery

from app.core.config import settings

celery = Celery(
    "ai3l_community",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Taipei",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery.conf.beat_schedule = {
    "retry-failed-events": {
        "task": "retry_failed_events",
        "schedule": 300.0,
    },
}

celery.autodiscover_tasks(["app.tasks"])
