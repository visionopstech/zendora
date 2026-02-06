from celery import Celery
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "zendora",
    broker=settings.get_celery_broker_url,
    backend=settings.get_celery_result_backend,
    include=["app.tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Optional: Configure task routes
celery_app.conf.task_routes = {
    "app.tasks.email.*": {"queue": "email"},
    "app.tasks.notifications.*": {"queue": "notifications"},
}
