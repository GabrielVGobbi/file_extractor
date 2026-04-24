"""Celery application factory (used only when ``ENABLE_CELERY=true``)."""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "fiscal_extractor",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 5,          # 5 minutes hard cap per task
    task_soft_time_limit=60 * 4,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
