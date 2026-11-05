import os
import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_celery_config.db")

from app.core.celery_app import celery_app


def test_celery_initialization_and_serialization():
    """Verify Celery app initializes with correct JSON serialization and UTC timezone."""
    assert celery_app.main == "wallet_management_tasks"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True


def test_celery_broker_and_result_backend_isolation():
    """Verify Celery uses isolated logical Redis DBs (DB 1 for broker, DB 2 for backend)."""
    broker = celery_app.conf.broker_url
    backend = celery_app.conf.result_backend

    assert broker is not None
    assert backend is not None
    assert "/0" not in broker, "Broker should not share Redis DB 0 (reserved for cache/rate-limiting)"
    assert "/0" not in backend, "Result backend should not share Redis DB 0"
    assert broker != backend, "Broker and result backend should use isolated databases"


def test_celery_worker_reliability_settings():
    """Verify Celery worker reliability and prefetch settings."""
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_track_started is True
    assert celery_app.conf.task_time_limit == 600
    assert celery_app.conf.task_soft_time_limit == 300
    assert celery_app.conf.result_expires == 86400


def test_celery_task_registration():
    """Verify all background tasks are properly registered with the Celery app."""
    registered = celery_app.tasks.keys()

    assert "app.jobs.daily_summary.generate_daily_summaries_task" in registered
    assert "app.jobs.daily_summary.generate_user_daily_summary_task" in registered
    assert "app.jobs.monthly_reminders.generate_monthly_reminders_task" in registered
    assert "app.jobs.excel_import.process_excel_import_task" in registered
    assert "app.jobs.notifications.dispatch_notification_task" in registered
    assert "app.jobs.notifications.dispatch_bulk_notifications_task" in registered
    assert "app.jobs.analytics.warm_user_analytics_cache_task" in registered


def test_celery_beat_schedule_configuration():
    """Verify Celery Beat periodic schedules for daily summary and monthly reminders."""
    schedule = celery_app.conf.beat_schedule
    assert "daily-financial-summary" in schedule
    assert "monthly-payment-reminders" in schedule

    daily_job = schedule["daily-financial-summary"]
    assert daily_job["task"] == "app.jobs.daily_summary.generate_daily_summaries_task"
    assert daily_job["options"]["queue"] == "scheduled"

    monthly_job = schedule["monthly-payment-reminders"]
    assert monthly_job["task"] == "app.jobs.monthly_reminders.generate_monthly_reminders_task"
    assert monthly_job["options"]["queue"] == "scheduled"


def test_task_queues_and_routing():
    """Verify task routing routes tasks to appropriate specialized queues."""
    routes = celery_app.conf.task_routes
    assert routes["app.jobs.excel_import.*"]["queue"] == "imports"
    assert routes["app.jobs.daily_summary.*"]["queue"] == "scheduled"
    assert routes["app.jobs.monthly_reminders.*"]["queue"] == "scheduled"
    assert routes["app.jobs.notifications.*"]["queue"] == "notifications"
    assert routes["app.jobs.analytics.*"]["queue"] == "default"
