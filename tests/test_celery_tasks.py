from datetime import date, datetime
from decimal import Decimal
import os
import tempfile
from unittest.mock import MagicMock, patch

from openpyxl import Workbook
import pytest
from sqlalchemy import select

os.environ["DATABASE_URL"] = "sqlite:///./test_celery_tasks.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from app.core.celery_app import celery_app
from app.database import engine, get_task_db, init_db
from app.jobs.analytics import warm_user_analytics_cache_task
from app.jobs.daily_summary import (
    generate_daily_summaries_task,
    generate_user_daily_summary_task,
)
from app.jobs.excel_import import process_excel_import_task
from app.jobs.monthly_reminders import generate_monthly_reminders_task
from app.jobs.notifications import (
    dispatch_bulk_notifications_task,
    dispatch_notification_task,
)
from app.models import (
    Base,
    ImportJob,
    MWallet,
    Notification,
    RecurringPayment,
    SWallet,
    Transaction,
    User,
)


@pytest.fixture(autouse=True)
def setup_test_db_and_celery():
    # Configure Celery in eager mode for synchronous deterministic test execution
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )


def _create_test_user(email: str = "celery_user@example.com", initial_balance: Decimal = Decimal("5000.00")) -> tuple[int, int, int]:
    with get_task_db() as db:
        user = User(
            name="Celery User",
            phone=f"99{abs(hash(email)) % 100000000:08d}",
            email=email,
            currency="INR",
            password_hash="fakehash",
        )
        db.add(user)
        db.flush()
        user_id = user.id

        super_wallet = SWallet(
            user_id=user_id,
            name="Main Super Wallet",
            currency="INR",
        )
        db.add(super_wallet)
        db.flush()
        super_wallet_id = super_wallet.id

        mini_wallet = MWallet(
            super_wallet_id=super_wallet_id,
            name="BANK",
            modeofpayment="BANK",
        )
        db.add(mini_wallet)
        db.flush()
        mini_wallet_id = mini_wallet.id

        if initial_balance > 0:
            init_tx = Transaction(
                super_wallet_id=super_wallet_id,
                mini_wallet_id=mini_wallet_id,
                amount=initial_balance,
                type="income",
                category="Initial Balance",
                modeofpayment="BANK",
                description="Opening balance",
                date_created=datetime.now(),
            )
            db.add(init_tx)

        db.commit()
        return user_id, super_wallet_id, mini_wallet_id


def _create_test_excel_file(rows: list[list]) -> tuple[str, str]:
    wb = Workbook()
    ws = wb.active
    ws.append(["amount", "type", "category", "date_created", "modeofpayment", "description", "proof"])
    for row in rows:
        ws.append(row)

    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    wb.save(path)
    wb.close()

    import hashlib
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return path, digest


def test_daily_summary_celery_task_execution_and_idempotency():
    user_id, super_wallet_id, mini_wallet_id = _create_test_user("daily_summary_task@example.com", initial_balance=Decimal("0.00"))
    today = date.today()

    # Add transaction
    with get_task_db() as db:
        tx = Transaction(
            super_wallet_id=super_wallet_id,
            mini_wallet_id=mini_wallet_id,
            amount=Decimal("1500.00"),
            type="income",
            category="Salary",
            modeofpayment="BANK",
            description="Monthly stipend",
            date_created=datetime.now(),
        )
        db.add(tx)
        db.commit()

    # Execute daily summary task via Celery
    res = generate_daily_summaries_task.delay(today.isoformat())
    assert res.successful()
    result_data = res.result
    assert result_data["status"] == "SUCCESS"
    assert result_data["summaries_generated"] == 1

    # Verify notification created in DB
    with get_task_db() as db:
        notifications = list(
            db.scalars(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.kind == "daily_summary",
                )
            )
        )
        assert len(notifications) == 1
        payload = notifications[0].payload
        assert payload["income"] == "1500.00"

    # Idempotency check: running again must generate 0 duplicate summaries
    res2 = generate_daily_summaries_task.delay(today.isoformat())
    assert res2.result["summaries_generated"] == 0

    with get_task_db() as db:
        count = len(list(db.scalars(select(Notification).where(Notification.user_id == user_id))))
        assert count == 1, "Duplicate notifications must never be created"


def test_user_daily_summary_task():
    user_id, _, _ = _create_test_user("user_summary_task@example.com")
    res = generate_user_daily_summary_task.delay(user_id=user_id)
    assert res.successful()
    assert res.result["status"] == "SUCCESS"
    assert res.result["generated"] is True

    # Unknown user returns failure gracefully
    unknown = generate_user_daily_summary_task.delay(user_id=999999)
    assert unknown.result["status"] == "FAILED"


def test_monthly_reminders_celery_task_execution_and_idempotency():
    user_id, _, _ = _create_test_user("reminders_task@example.com")

    with get_task_db() as db:
        payment = RecurringPayment(
            user_id=user_id,
            name="Broadband Internet",
            amount=Decimal("899.00"),
            category="Utilities",
            due_day=15,
            frequency="monthly",
            active=True,
        )
        db.add(payment)
        db.commit()

    # Execute monthly reminders task via Celery
    res = generate_monthly_reminders_task.delay("2026-11-01")
    assert res.successful()
    assert res.result["status"] == "SUCCESS"
    assert res.result["reminders_generated"] == 1

    with get_task_db() as db:
        notifs = list(
            db.scalars(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.kind == "recurring_payment_reminder",
                )
            )
        )
        assert len(notifs) == 1
        assert "Broadband Internet" in notifs[0].message
        assert notifs[0].payload["due_date"] == "2026-11-15"

    # Idempotency check: running again must generate 0 duplicate reminders
    res2 = generate_monthly_reminders_task.delay("2026-11-01")
    assert res2.result["reminders_generated"] == 0


def test_async_excel_import_task_success_and_cleanup():
    user_id, super_wallet_id, _ = _create_test_user("async_import_success@example.com", initial_balance=Decimal("0.00"))
    rows = [
        [Decimal("1000.00"), "income", "Freelance", "2026-11-02", "BANK", "Project payout", None],
        [Decimal("300.00"), "expense", "Groceries", "2026-11-02", "BANK", "Supermarket", None],
    ]
    file_path, sha = _create_test_excel_file(rows)

    with get_task_db() as db:
        job = ImportJob(
            id="job-success-123",
            user_id=user_id,
            status="PENDING",
            filename="transactions.xlsx",
            file_sha256=sha,
        )
        db.add(job)
        db.commit()

    res = process_excel_import_task.delay(
        import_job_id="job-success-123",
        super_wallet_id=super_wallet_id,
        user_id=user_id,
        file_path=file_path,
        preview_sha256=sha,
    )
    assert res.successful()
    assert res.result["status"] == "COMPLETED"
    assert res.result["imported_count"] == 2

    # Verify ImportJob state in database
    with get_task_db() as db:
        db_job = db.get(ImportJob, "job-success-123")
        assert db_job.status == "COMPLETED"
        assert db_job.imported_count == 2
        assert db_job.total_rows == 2
        assert db_job.date_completed is not None

        # Verify transactions exist in DB
        txs = list(db.scalars(select(Transaction).where(Transaction.super_wallet_id == super_wallet_id)))
        assert len(txs) == 2

    # Verify staged file was cleaned up from disk
    assert not os.path.exists(file_path), "Staged file should be deleted after processing"


def test_async_excel_import_validation_failure_marks_job_failed():
    user_id, super_wallet_id, _ = _create_test_user("async_import_fail@example.com", initial_balance=Decimal("0.00"))
    # Expense of 99999 exceeds available balance of 0
    rows = [
        [Decimal("99999.00"), "expense", "Luxury", "2026-11-02", "BANK", "Overspend", None],
    ]
    file_path, sha = _create_test_excel_file(rows)

    with get_task_db() as db:
        job = ImportJob(
            id="job-fail-456",
            user_id=user_id,
            status="PENDING",
            filename="overspend.xlsx",
            file_sha256=sha,
        )
        db.add(job)
        db.commit()

    res = process_excel_import_task.delay(
        import_job_id="job-fail-456",
        super_wallet_id=super_wallet_id,
        user_id=user_id,
        file_path=file_path,
        preview_sha256=sha,
    )
    assert res.successful()
    assert res.result["status"] == "FAILED"

    with get_task_db() as db:
        db_job = db.get(ImportJob, "job-fail-456")
        assert db_job.status == "FAILED"
        assert db_job.imported_count == 0
        assert db_job.error_details is not None
        # No transactions should be created
        txs = list(db.scalars(select(Transaction).where(Transaction.super_wallet_id == super_wallet_id)))
        assert len(txs) == 0

    assert not os.path.exists(file_path), "Staged file should be cleaned up even on failure"


def test_notification_dispatch_tasks():
    user_id, _, _ = _create_test_user("notif_task_test@example.com")

    # Single dispatch
    res = dispatch_notification_task.delay(
        user_id=user_id,
        kind="alert",
        message="Test alert message",
        payload={"level": "warning"},
        dedupe_key="test-alert-key-1",
    )
    assert res.result["status"] == "SUCCESS"

    # Duplicate dispatch skipped
    dup = dispatch_notification_task.delay(
        user_id=user_id,
        kind="alert",
        message="Test alert message",
        payload={"level": "warning"},
        dedupe_key="test-alert-key-1",
    )
    assert dup.result["status"] == "SKIPPED"

    # Bulk dispatch
    bulk_res = dispatch_bulk_notifications_task.delay(
        [
            {"user_id": user_id, "kind": "info", "message": "Bulk 1", "dedupe_key": "bulk-1"},
            {"user_id": user_id, "kind": "info", "message": "Bulk 2", "dedupe_key": "bulk-2"},
        ]
    )
    assert bulk_res.result["status"] == "SUCCESS"
    assert bulk_res.result["created_count"] == 2


def test_analytics_warm_cache_task():
    user_id, _, _ = _create_test_user("analytics_warm@example.com")
    with patch("redis.Redis.from_url") as mock_redis:
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        res = warm_user_analytics_cache_task.delay(user_id=user_id)
        assert res.result["status"] == "SUCCESS"
        assert mock_client.set.call_count == 2
