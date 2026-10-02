import os

os.environ["DATABASE_URL"] = "sqlite:///./test_wallet_phase1.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def reset_db():
    from app.database import engine
    from app.models import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_register_login_and_me_endpoint():
    reset_db()

    response = client.post(
        "/auth/register",
        json={
            "name": "Alice",
            "phone": "1111111111",
            "email": "alice@example.com",
            "currency": "INR",
            "password": "StrongPass!123",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "password" not in body

    login = client.post(
        "/auth/login",
        json={
            "email": "alice@example.com",
            "password": "StrongPass!123",
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert token

    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "alice@example.com"


def test_super_wallet_is_limited_to_one_per_user_and_mini_wallets_are_owned():
    reset_db()

    user_a = client.post(
        "/auth/register",
        json={
            "name": "Alice",
            "phone": "1111111111",
            "email": "alice@example.com",
            "currency": "INR",
            "password": "StrongPass!123",
        },
    )
    user_b = client.post(
        "/auth/register",
        json={
            "name": "Bob",
            "phone": "2222222222",
            "email": "bob@example.com",
            "currency": "INR",
            "password": "StrongPass!123",
        },
    )

    token_a = client.post(
        "/auth/login",
        json={
            "email": "alice@example.com",
            "password": "StrongPass!123",
        },
    ).json()["access_token"]
    token_b = client.post(
        "/auth/login",
        json={
            "email": "bob@example.com",
            "password": "StrongPass!123",
        },
    ).json()["access_token"]

    first = client.post(
        "/super-wallet",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Primary Wallet", "currency": "INR"},
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/super-wallet",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Second Wallet", "currency": "INR"},
    )
    assert second.status_code == 400, second.text

    mini = client.post(
        "/super-wallet/mini-wallets",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Cash", "modeofpayment": "Cash"},
    )
    assert mini.status_code == 201, mini.text
    mini_id = mini.json()["id"]

    access_other = client.get(
        f"/mini-wallets/{mini_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert access_other.status_code == 403, access_other.text

    no_token = client.get("/users/me")
    assert no_token.status_code == 401, no_token.text
