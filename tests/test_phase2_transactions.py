import os

os.environ["DATABASE_URL"] = "sqlite:///./test_wallet_phase2.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def reset_db():
    from app.database import engine
    from app.models import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_user(email: str, name: str = "User"):
    response = client.post(
        "/auth/register",
        json={
            "name": name,
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


def test_transaction_balance_and_ownership_work_for_mini_wallets():
    reset_db()

    token_a = create_user("alice@example.com", "Alice")
    token_b = create_user("bob@example.com", "Bob")

    super_a = client.post(
        "/super-wallet",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Primary Wallet", "currency": "INR"},
    )
    assert super_a.status_code == 201, super_a.text

    mini = client.post(
        "/super-wallet/mini-wallets",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Cash", "modeofpayment": "Cash"},
    )
    assert mini.status_code == 201, mini.text
    mini_id = mini.json()["id"]

    income = client.post(
        f"/mini-wallets/{mini_id}/transactions",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "amount": "5000.00",
            "type": "income",
            "category": "salary",
            "description": "Monthly salary",
            "modeofpayment": "bank",
            "proof": "paystub",
            "date_created": "2026-01-15T09:30:00",
        },
    )
    assert income.status_code == 201, income.text
    assert income.json()["amount"] == "5000.00"

    balance_after_income = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert balance_after_income.status_code == 200, balance_after_income.text
    assert balance_after_income.json()["balance"] == "5000.00"

    expense = client.post(
        f"/mini-wallets/{mini_id}/transactions",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "amount": "1200.00",
            "type": "expense",
            "category": "food",
            "description": "Groceries",
            "modeofpayment": "cash",
            "proof": "receipt",
            "date_created": "2026-01-16T08:15:00",
        },
    )
    assert expense.status_code == 201, expense.text
    assert expense.json()["type"] == "expense"

    balance_after_expense = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert balance_after_expense.json()["balance"] == "3800.00"

    super_balance = client.get(
        "/super-wallet/balance",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert super_balance.status_code == 200, super_balance.text
    assert super_balance.json()["balance"] == "3800.00"

    other_user = client.get(
        f"/mini-wallets/{mini_id}/transactions",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert other_user.status_code == 403, other_user.text

    history = client.get(
        f"/mini-wallets/{mini_id}/transactions",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert history.status_code == 200, history.text
    assert len(history.json()) == 2

    updated = client.put(
        f"/transactions/{income.json()['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "amount": "6000.00",
            "type": "income",
            "date_created": "2026-01-15T09:30:00",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["amount"] == "6000.00"

    after_update = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert after_update.json()["balance"] == "4800.00"

    deleted = client.delete(
        f"/transactions/{expense.json()['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert deleted.status_code == 204, deleted.text

    final_balance = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert final_balance.json()["balance"] == "6000.00"
