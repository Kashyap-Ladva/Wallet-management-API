import os
from decimal import Decimal

os.environ["DATABASE_URL"] = "sqlite:///./test_wallet_integrity.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def reset_db():
    from app.database import engine
    from app.models import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def register_and_login(email: str, name: str = "User") -> tuple[str, int]:
    reg = client.post(
        "/auth/register",
        json={
            "name": name,
            "phone": str(2000000000 + len(email)),
            "email": email,
            "currency": "INR",
            "password": "SecurePassword123!",
        },
    )
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["id"]

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"], user_id


def setup_wallet(token: str) -> int:
    client.post(
        "/super-wallet",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Main Super Wallet", "currency": "INR"},
    )
    mini = client.post(
        "/super-wallet/mini-wallets",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Checking Account", "modeofpayment": "bank"},
    )
    assert mini.status_code == 201, mini.text
    return mini.json()["id"]


def test_financial_integrity_flow():
    """
    Mandatory financial integrity test sequence:
    1. Starting balance = 0
    2. + income 10000 = 10000
    3. - expense 2000 = 8000
    4. Update expense 2000 -> 3000 = 7000
    5. Delete expense = 10000
    6. Switch income to expense & expense to income
    """
    reset_db()
    token, _ = register_and_login("fin_test@example.com", "Financial Tester")
    mini_id = setup_wallet(token)

    # 1. Starting balance must be 0
    bal_res = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bal_res.status_code == 200
    assert bal_res.json()["balance"] == "0.00"

    # 2. Add income 10000
    inc_res = client.post(
        f"/mini-wallets/{mini_id}/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "amount": "10000.00",
            "type": "income",
            "category": "Salary",
            "modeofpayment": "bank",
            "description": "Initial Salary",
        },
    )
    assert inc_res.status_code == 201, inc_res.text
    inc_id = inc_res.json()["id"]

    bal_res = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bal_res.json()["balance"] == "10000.00"

    # 3. Add expense 2000
    exp_res = client.post(
        f"/mini-wallets/{mini_id}/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "amount": "2000.00",
            "type": "expense",
            "category": "Rent",
            "modeofpayment": "bank",
            "description": "Office rent",
        },
    )
    assert exp_res.status_code == 201, exp_res.text
    exp_id = exp_res.json()["id"]

    bal_res = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bal_res.json()["balance"] == "8000.00"

    # 4. Update expense 2000 -> 3000 (net effect -1000)
    upd_res = client.put(
        f"/transactions/{exp_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "3000.00"},
    )
    assert upd_res.status_code == 200, upd_res.text

    bal_res = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bal_res.json()["balance"] == "7000.00"

    # Super wallet balance must also equal 7000.00
    super_bal = client.get(
        "/super-wallet/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert super_bal.json()["balance"] == "7000.00"

    # 5. Delete expense (balance restored to 10000.00)
    del_res = client.delete(
        f"/transactions/{exp_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 204

    bal_res = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bal_res.json()["balance"] == "10000.00"

    # 6. Insufficient balance protection: expense exceeding available balance is rejected
    excess_res = client.post(
        f"/mini-wallets/{mini_id}/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "amount": "15000.00",
            "type": "expense",
            "category": "Car",
            "modeofpayment": "bank",
        },
    )
    assert excess_res.status_code == 400
    assert "Insufficient balance" in excess_res.text

    # Balance must remain unchanged at 10000.00
    bal_res = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bal_res.json()["balance"] == "10000.00"

    # 7. Add expense 4000, then switch it to income 4000
    exp2_res = client.post(
        f"/mini-wallets/{mini_id}/transactions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "amount": "4000.00",
            "type": "expense",
            "category": "Equipment",
            "modeofpayment": "bank",
        },
    )
    assert exp2_res.status_code == 201
    exp2_id = exp2_res.json()["id"]

    bal_res = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bal_res.json()["balance"] == "6000.00"

    # Switch expense 4000 -> income 4000: reverses -4000 and adds +4000 => net +8000 => 14000.00
    switch_res = client.put(
        f"/transactions/{exp2_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"type": "income"},
    )
    assert switch_res.status_code == 200, switch_res.text

    bal_res = client.get(
        f"/mini-wallets/{mini_id}/balance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bal_res.json()["balance"] == "14000.00"


def test_savings_and_debt_atomicity_and_invariants():
    reset_db()
    token, _ = register_and_login("savings_debt@example.com", "Savings User")

    # Test Savings Goal Withdrawal Exceeding Balance
    goal = client.post(
        "/savings",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Emergency Fund", "target_amount": "5000.00"},
    )
    assert goal.status_code == 201
    goal_id = goal.json()["id"]

    # Contribute 1000
    contrib = client.post(
        f"/savings/{goal_id}/contributions",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "1000.00", "action": "add"},
    )
    assert contrib.status_code == 200
    assert contrib.json()["current_amount"] == "1000.00"

    # Withdraw 1500 (should fail with 400)
    over_withdraw = client.post(
        f"/savings/{goal_id}/contributions",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "1500.00", "action": "withdraw"},
    )
    assert over_withdraw.status_code == 400

    # Ensure amount is still 1000
    goals = client.get("/savings", headers={"Authorization": f"Bearer {token}"})
    assert goals.json()[0]["current_amount"] == "1000.00"

    # Test Debt Repayment Exceeding Remaining Amount
    debt = client.post(
        "/debts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "person": "John",
            "direction": "lent",
            "amount": "2000.00",
            "date": "2026-01-01",
        },
    )
    assert debt.status_code == 201
    debt_id = debt.json()["id"]

    # Repay 1000
    repay1 = client.post(
        f"/debts/{debt_id}/repayments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "1000.00", "date": "2026-01-10"},
    )
    assert repay1.status_code == 201, repay1.text

    # Repay 1500 (exceeds remaining 1000 -> should fail with 400)
    over_repay = client.post(
        f"/debts/{debt_id}/repayments",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": "1500.00", "date": "2026-01-15"},
    )
    assert over_repay.status_code == 400

    # Ensure remaining amount is still 1000
    debts = client.get("/debts", headers={"Authorization": f"Bearer {token}"})
    assert debts.json()[0]["remaining_amount"] == "1000.00"
    assert debts.json()[0]["status"] == "partially_paid"
