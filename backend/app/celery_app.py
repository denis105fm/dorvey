"""Celery app."""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "dorvey",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.doorway_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    beat_schedule={
        "cron-daily": {
            "task": "app.tasks.doorway_tasks.cron_run_all",
            "schedule": crontab(hour=3, minute=0),
        },
        "auto-generate-daily": {
            "task": "app.tasks.doorway_tasks.auto_generate_from_keywords",
            "schedule": crontab(hour=4, minute=30),
            "kwargs": {"max_per_run": 20},
        },
        "collect-server-metrics": {
            "task": "app.tasks.doorway_tasks.collect_server_metrics",
            "schedule": crontab(minute="*/5"),
        },
    },
)
