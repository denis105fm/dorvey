"""Celery app."""

from celery import Celery
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
)
