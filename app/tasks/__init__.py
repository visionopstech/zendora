"""
Celery tasks module.

This module contains all background tasks that can be executed asynchronously.
"""
from app.tasks.email_tasks import send_email_task
from app.tasks.example_tasks import add_numbers, process_data

__all__ = [
    "send_email_task",
    "add_numbers",
    "process_data",
]
