import os
from datetime import date
from io import BytesIO

os.environ["DATABASE_URL"] = "sqlite:///./test_wallet_phase4.db"

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app

client = TestClient(app)


def reset_db():
    from app.database import engine
    from app.models import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_user(email: str = "phase4@example.com") -> str:
    registered = client.post(
        "/auth/register",
        json={
            "name": "Phase Four",
            "phone": str(1000000000 + len(email)),
            "email": email,
            "currency": "INR",
            "password": "StrongPass!123",
        },
    )
    assert registered.status_code == 201, registered.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass!123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_wallet(token: str) -> int:
    created = client.post(
        "/super-wallet",
        headers=auth(token),
        json={"name": "Primary", "currency": "INR"},
    )
    assert created.status_code == 201, created.text
    mini = client.post(
        "/super-wallet/mini-wallets",
        headers=auth(token),
        json={"name": "Cash", "modeofpayment": "cash"},
    )
    assert mini.status_code == 201, mini.text
    return mini.json()["id"]


def workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(
        [
            "amount",
            "type",
            "category",
            "date_created",
            "modeofpayment",
            "description",
            "proof",
        ]
    )
    for row in rows:
        worksheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def upload(content: bytes) -> dict:
    return {
        "file": (
            "transactions.xlsx",
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


def test_excel_import_preview_confirm_and_reject_invalid_batch():
    reset_db()
    token = create_user()
    mini_wallet_id = create_wallet(token)
    content = workbook_bytes(
        [
            [5000, "income", "salary", date(2026, 10, 1), "bank", "Salary", None],
            [1200, "expense", "food", date(2026, 10, 2), "cash", "Groceries", "receipt"],
        ]
    )
    data = {"mini_wallet_id": str(mini_wallet_id)}
    preview = client.post(
        "/imports/excel/preview",
        headers=auth(token),
        data=data,
        files=upload(content),
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["valid"] is True
    assert len(preview.json()["rows"]) == 2
    assert preview.json()["duplicate_policy"].startswith("Duplicate rows are imported")

    confirmed = client.post(
        "/imports/excel/confirm",
        headers=auth(token),
        data={
            **data,
            "preview_sha256": preview.json()["file_sha256"],
        },
        files=upload(content),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["imported_count"] == 2
    balance = client.get(
        f"/mini-wallets/{mini_wallet_id}/balance",
        headers=auth(token),
    )
    assert balance.status_code == 200, balance.text
    assert balance.json()["balance"] == "3800.00"

    duplicate_confirmed = client.post(
        "/imports/excel/confirm",
        headers=auth(token),
        data={
            **data,
            "preview_sha256": preview.json()["file_sha256"],
        },
        files=upload(content),
    )
    assert duplicate_confirmed.status_code == 200, duplicate_confirmed.text
    assert duplicate_confirmed.json()["imported_count"] == 2
    duplicate_balance = client.get(
        f"/mini-wallets/{mini_wallet_id}/balance",
        headers=auth(token),
    )
    assert duplicate_balance.json()["balance"] == "7600.00"

    overspending_file = workbook_bytes(
        [[8000, "expense", "rent", date(2026, 10, 3), "bank", "Too much", None]]
    )
    overspending_preview = client.post(
        "/imports/excel/preview",
        headers=auth(token),
        data=data,
        files=upload(overspending_file),
    )
    assert overspending_preview.status_code == 200, overspending_preview.text
    assert overspending_preview.json()["valid"] is False
    assert overspending_preview.json()["errors"][0]["row"] == 2

    changed_file = workbook_bytes(
        [[100, "expense", "food", date(2026, 10, 3), "cash", "Changed", None]]
    )
    changed = client.post(
        "/imports/excel/confirm",
        headers=auth(token),
        data={
            **data,
            "preview_sha256": preview.json()["file_sha256"],
        },
        files=upload(changed_file),
    )
    assert changed.status_code == 409, changed.text

    invalid = workbook_bytes(
        [[100, "invalid", "food", "not-a-date", "cash", "Bad row", None]]
    )
    invalid_preview = client.post(
        "/imports/excel/preview",
        headers=auth(token),
        data=data,
        files=upload(invalid),
    )
    assert invalid_preview.status_code == 200, invalid_preview.text
    assert invalid_preview.json()["valid"] is False
    assert len(invalid_preview.json()["errors"]) == 1
    rejected = client.post(
        "/imports/excel/confirm",
        headers=auth(token),
        data={
            **data,
            "preview_sha256": invalid_preview.json()["file_sha256"],
        },
        files=upload(invalid),
    )
    assert rejected.status_code == 422, rejected.text


def test_savings_investment_debt_and_recurring_payment_ownership():
    reset_db()
    token = create_user()
    other_token = create_user("other-phase4@example.com")

    goal = client.post(
        "/savings",
        headers=auth(token),
        json={"name": "Emergency fund", "target_amount": "1000.00"},
    )
    assert goal.status_code == 201, goal.text
    goal_id = goal.json()["id"]
    contribution = client.post(
        f"/savings/{goal_id}/contributions",
        headers=auth(token),
        json={"amount": "600.00", "action": "add"},
    )
    assert contribution.status_code == 200, contribution.text
    assert contribution.json()["current_amount"] == "600.00"
    assert float(contribution.json()["progress_percentage"]) == 60.0
    withdrawal = client.post(
        f"/savings/{goal_id}/contributions",
        headers=auth(token),
        json={"amount": "601.00", "action": "withdraw"},
    )
    assert withdrawal.status_code == 400
    hidden_goal = client.delete(f"/savings/{goal_id}", headers=auth(other_token))
    assert hidden_goal.status_code == 404

    investment = client.post(
        "/investments",
        headers=auth(token),
        json={
            "name": "Index fund",
            "amount": "2500.00",
            "investment_type": "mutual_fund",
            "date": "2026-10-01",
        },
    )
    assert investment.status_code == 201, investment.text
    investment_id = investment.json()["id"]
    assert client.get(
        f"/investments/{investment_id}",
        headers=auth(other_token),
    ).status_code == 404
    updated_investment = client.put(
        f"/investments/{investment_id}",
        headers=auth(token),
        json={"notes": "Long-term"},
    )
    assert updated_investment.status_code == 200, updated_investment.text
    assert updated_investment.json()["notes"] == "Long-term"

    debt = client.post(
        "/debts",
        headers=auth(token),
        json={
            "person": "Alex",
            "direction": "lent",
            "amount": "500.00",
            "date": "2026-09-01",
            "due_date": "2026-12-01",
        },
    )
    assert debt.status_code == 201, debt.text
    debt_id = debt.json()["id"]
    repayment = client.post(
        f"/debts/{debt_id}/repayments",
        headers=auth(token),
        json={"amount": "200.00", "date": "2026-10-01"},
    )
    assert repayment.status_code == 201, repayment.text
    partial = client.get("/debts", headers=auth(token))
    assert partial.json()[0]["remaining_amount"] == "300.00"
    assert partial.json()[0]["status"] == "partially_paid"
    excess = client.post(
        f"/debts/{debt_id}/repayments",
        headers=auth(token),
        json={"amount": "301.00", "date": "2026-10-02"},
    )
    assert excess.status_code == 400

    recurring = client.post(
        "/recurring-payments",
        headers=auth(token),
        json={
            "name": "Rent",
            "amount": "1200.00",
            "category": "housing",
            "due_day": 31,
        },
    )
    assert recurring.status_code == 201, recurring.text
    assert recurring.json()["frequency"] == "monthly"
    assert client.get(
        "/recurring-payments",
        headers=auth(other_token),
    ).json() == []


def test_scheduled_jobs_persist_idempotent_user_notifications():
    reset_db()
    token = create_user()
    mini_wallet_id = create_wallet(token)
    created_transaction = client.post(
        f"/mini-wallets/{mini_wallet_id}/transactions",
        headers=auth(token),
        json={
            "amount": "1000.00",
            "type": "income",
            "category": "salary",
            "modeofpayment": "bank",
            "date_created": "2026-10-08T09:00:00",
        },
    )
    assert created_transaction.status_code == 201, created_transaction.text
    recurring = client.post(
        "/recurring-payments",
        headers=auth(token),
        json={
            "name": "Electricity",
            "amount": "100.00",
            "category": "utilities",
            "due_day": 31,
        },
    )
    assert recurring.status_code == 201, recurring.text

    from app.database import SessionLocal
    from app.jobs.daily_summary import generate_daily_summaries
    from app.jobs.monthly_reminders import generate_monthly_reminders

    with SessionLocal() as db:
        assert generate_daily_summaries(db, date(2026, 10, 8)) == 1
        assert generate_daily_summaries(db, date(2026, 10, 8)) == 0
        assert generate_monthly_reminders(db, date(2026, 2, 1)) == 1
        assert generate_monthly_reminders(db, date(2026, 2, 1)) == 0

    notifications = client.get("/notifications", headers=auth(token))
    assert notifications.status_code == 200, notifications.text
    kinds = {item["kind"] for item in notifications.json()}
    assert kinds == {"daily_summary", "recurring_payment_reminder"}
    reminder = next(
        item for item in notifications.json()
        if item["kind"] == "recurring_payment_reminder"
    )
    assert reminder["payload"]["due_date"] == "2026-02-28"
    read = client.post(
        f"/notifications/{reminder['id']}/read",
        headers=auth(token),
    )
    assert read.status_code == 200, read.text
    assert read.json()["read_at"] is not None

    with TestClient(app) as lifespan_client:
        assert lifespan_client.get("/health").status_code == 200
        assert app.state.scheduler.running


def test_transaction_proof_upload_retrieval_and_ownership(tmp_path, monkeypatch):
    reset_db()
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path))
    token = create_user()
    other_token = create_user("other-proof@example.com")
    mini_wallet_id = create_wallet(token)
    created = client.post(
        f"/mini-wallets/{mini_wallet_id}/transactions",
        headers=auth(token),
        json={
            "amount": "100.00",
            "type": "income",
            "category": "other",
            "modeofpayment": "cash",
        },
    )
    assert created.status_code == 201, created.text
    transaction_id = created.json()["id"]

    text_proof = client.post(
        f"/transactions/{transaction_id}/proof",
        headers=auth(token),
        data={"text": "Receipt reference A-123"},
    )
    assert text_proof.status_code == 200, text_proof.text
    assert text_proof.json()["kind"] == "text"
    assert client.get(
        f"/transactions/{transaction_id}/proof",
        headers=auth(token),
    ).json()["proof"] == "Receipt reference A-123"

    image_content = b"\x89PNG\r\n\x1a\n" + b"phase4-test-image"
    image_proof = client.post(
        f"/transactions/{transaction_id}/proof",
        headers=auth(token),
        files={"file": ("receipt.png", image_content, "image/png")},
    )
    assert image_proof.status_code == 200, image_proof.text
    assert image_proof.json()["kind"] == "image"
    retrieved_image = client.get(
        f"/transactions/{transaction_id}/proof",
        headers=auth(token),
    )
    assert retrieved_image.status_code == 200
    assert retrieved_image.content == image_content
    assert retrieved_image.headers["content-type"] == "image/png"
    stored_image_path = tmp_path / "proofs" / image_proof.json()["proof"].split("/")[-1]
    assert stored_image_path.is_file()

    forbidden = client.get(
        f"/transactions/{transaction_id}/proof",
        headers=auth(other_token),
    )
    assert forbidden.status_code == 403
    invalid_image = client.post(
        f"/transactions/{transaction_id}/proof",
        headers=auth(token),
        files={"file": ("fake.png", b"not an image", "image/png")},
    )
    assert invalid_image.status_code == 422
    deleted = client.delete(
        f"/transactions/{transaction_id}",
        headers=auth(token),
    )
    assert deleted.status_code == 204
    assert not stored_image_path.exists()
