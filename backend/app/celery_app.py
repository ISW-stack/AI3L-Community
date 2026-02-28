from celery import Celery
from celery.schedules import crontab

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
    "cleanup-stale-guests": {
        "task": "app.tasks.guest_cleanup.cleanup_stale_guests",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3:00 AM
    },
}

celery.autodiscover_tasks(["app.tasks"])
