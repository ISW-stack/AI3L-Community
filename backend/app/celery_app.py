from celery import Celery

from app.core.config import settings

celery = Celery(
    "ai3l_community",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.event_retry",
        "app.tasks.cleanup",
        "app.tasks.form_export",
        "app.tasks.form_autoclose",
        "app.tasks.virustotal",
        "app.tasks.thumbnail",
        "app.tasks.recommendations",
        "app.tasks.view_sync",
    ],
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
    result_expires=86400,
    task_soft_time_limit=300,
    task_time_limit=600,
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    worker_max_memory_per_child=262144,
)

celery.conf.beat_schedule = {
    "retry-failed-events": {
        "task": "retry_failed_events",
        "schedule": 300.0,
        "options": {"soft_time_limit": 250, "time_limit": 300},
    },
    "cleanup-orphan-files": {
        "task": "cleanup_orphan_files",
        "schedule": 604800.0,  # every 7 days
        "options": {"soft_time_limit": 3500, "time_limit": 3600},
    },
    "sync-guest-counter": {
        "task": "sync_guest_counter",
        "schedule": 300.0,  # every 5 minutes
        "options": {"soft_time_limit": 30, "time_limit": 60},
    },
    "cleanup-old-file-scans": {
        "task": "cleanup_old_file_scans",
        "schedule": 86400.0,  # every 24 hours
        "options": {"soft_time_limit": 60, "time_limit": 120},
    },
    "compute-friend-recommendations": {
        "task": "compute_friend_recommendations",
        "schedule": 86400.0,  # daily
        "options": {"soft_time_limit": 600, "time_limit": 900},
    },
    "reconcile-counters": {
        "task": "reconcile_counters",
        "schedule": 21600.0,  # every 6 hours
        "options": {"soft_time_limit": 300, "time_limit": 600},
    },
    "auto-close-expired-forms": {
        "task": "auto_close_expired_forms",
        "schedule": 300.0,  # every 5 minutes
        "options": {"soft_time_limit": 30, "time_limit": 60},
    },
}
