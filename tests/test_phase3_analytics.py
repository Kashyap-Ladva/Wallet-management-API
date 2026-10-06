import os

os.environ["DATABASE_URL"] = "sqlite:///./test_wallet_phase3.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def reset_db():
    from app.database import engine
    from app.models import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_user(email: str):
    response = client.post(
        "/auth/register",
        json={
            "name": "Alice",
            "phone": str(1000000000 + len(email)),
            "email": email,
            "currency": "INR",
            "password": "StrongPass!123",
        },
    )
    assert response.status_code == 201, response.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "StrongPass!123"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_phase3_analytics_and_budget_endpoints():
    reset_db()
    token = create_user("alice@example.com")

    wallet = client.post(
        "/super-wallet",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Primary Wallet", "currency": "INR"},
    )
    assert wallet.status_code == 201, wallet.text

    mini = client.post(
        "/super-wallet/mini-wallets",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Cash", "modeofpayment": "Cash"},
    )
    assert mini.status_code == 201, mini.text
    mini_id = mini.json()["id"]

    for payload in [
        {
            "amount": "25000.00",
            "type": "income",
            "category": "salary",
            "description": "Monthly salary",
            "modeofpayment": "bank",
            "proof": "paystub",
            "date_created": "2026-01-05T09:30:00",
        },
        {
            "amount": "3000.00",
            "type": "expense",
            "category": "food",
            "description": "Groceries",
            "modeofpayment": "cash",
            "proof": "receipt",
            "date_created": "2026-01-15T08:15:00",
        },
        {
            "amount": "2000.00",
            "type": "expense",
            "category": "travel",
            "description": "Train ticket",
            "modeofpayment": "upi",
            "proof": "ticket",
            "date_created": "2026-01-20T12:00:00",
        },
        {
            "amount": "10000.00",
            "type": "expense",
            "category": "rent",
            "description": "Apartment rent",
            "modeofpayment": "bank",
            "proof": "lease",
            "date_created": "2026-01-31T18:00:00",
        },
    ]:
        response = client.post(
            f"/mini-wallets/{mini_id}/transactions",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert response.status_code == 201, response.text

    daily = client.get(
        "/analytics/daily",
        params={"date": "2026-01-15"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert daily.status_code == 200, daily.text
    assert daily.json()["income"] == "0.00"
    assert daily.json()["expense"] == "3000.00"
    assert daily.json()["net"] == "-3000.00"

    monthly = client.get(
        "/analytics/monthly",
        params={"year": 2026, "month": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert monthly.status_code == 200, monthly.text
    assert monthly.json()["total_income"] == "25000.00"
    assert monthly.json()["total_expense"] == "15000.00"
    assert monthly.json()["net"] == "10000.00"

    yearly = client.get(
        "/analytics/yearly",
        params={"year": 2026},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert yearly.status_code == 200, yearly.text
    assert yearly.json()["January"]["total_expense"] == "15000.00"

    categories = client.get(
        "/analytics/categories",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert categories.status_code == 200, categories.text
    assert any(item["category"] == "food" and item["total"] == "3000.00" for item in categories.json())

    pie = client.get(
        "/analytics/expenses/pie",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pie.status_code == 200, pie.text
    assert pie.json()["labels"]
    assert pie.json()["values"]

    bar = client.get(
        "/analytics/expenses/bar",
        params={"year": 2026},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bar.status_code == 200, bar.text
    assert "labels" in bar.json()
    assert "values" in bar.json()

    budget_res = client.post(
        "/budgets",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Food target",
            "period": "monthly",
            "amount": "20000.00",
            "category": "food",
        },
    )
    assert budget_res.status_code == 201, budget_res.text
    budget_id = budget_res.json()["id"]

    status = client.get(
        f"/budgets/{budget_id}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status.status_code == 200, status.text
    assert status.json()["target"] == "20000.00"
    assert status.json()["spent"] == "3000.00"
    assert status.json()["remaining"] == "17000.00"
    assert status.json()["exceeded"] is False

    budgets = client.get("/budgets", headers={"Authorization": f"Bearer {token}"})
    assert budgets.status_code == 200, budgets.text
    assert len(budgets.json()) == 1
