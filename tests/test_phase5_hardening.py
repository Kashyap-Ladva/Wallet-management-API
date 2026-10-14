import os

os.environ["DATABASE_URL"] = "sqlite:///./test_wallet_hardening.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def reset_db():
    from app.database import engine
    from app.models import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


import itertools

_phone_counter = itertools.count(1000)


def register_and_login(email: str, name: str = "User") -> str:
    res = client.post(
        "/auth/register",
        json={
            "name": name,
            "phone": f"30{next(_phone_counter):08d}",
            "email": email,
            "currency": "USD",
            "password": "Password123!",
        },
    )
    assert res.status_code == 201, res.text

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_and_observability_middleware():
    reset_db()

    # Test /health endpoint
    res = client.get("/health")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"
    assert "scheduler" in body

    # Test security headers and request id
    assert "x-request-id" in res.headers
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"

    # Test custom request ID propagation
    custom_id = "test-custom-request-id-999"
    res_custom = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res_custom.headers["x-request-id"] == custom_id


def test_authentication_and_token_failure_cases():
    reset_db()

    # Unauthenticated protected request
    unauth = client.get("/users/me")
    assert unauth.status_code == 401
    assert "Authentication required" in unauth.text

    # Invalid token
    invalid_token = client.get("/users/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert invalid_token.status_code == 401

    # Registration validation: password < 8 chars
    weak_pw = client.post(
        "/auth/register",
        json={
            "name": "Weak",
            "phone": "3111111111",
            "email": "weak@example.com",
            "currency": "USD",
            "password": "short",
        },
    )
    assert weak_pw.status_code == 422

    # Duplicate registration
    token_a = register_and_login("dup_user@example.com")
    dup_res = client.post(
        "/auth/register",
        json={
            "name": "Dup",
            "phone": "3999999999",
            "email": "dup_user@example.com",
            "currency": "USD",
            "password": "Password123!",
        },
    )
    assert dup_res.status_code == 400
    assert "Email already registered" in dup_res.text


def test_cross_user_authorization_isolation():
    reset_db()

    token_a = register_and_login("user_a@example.com", "Alice")
    token_b = register_and_login("user_b@example.com", "Bob")

    # Alice sets up super-wallet, mini-wallet, budget, and transaction
    client.post("/super-wallet", headers=auth(token_a), json={"name": "Alice Super", "currency": "USD"})
    mini_a = client.post("/super-wallet/mini-wallets", headers=auth(token_a), json={"name": "Alice Mini", "modeofpayment": "bank"}).json()["id"]

    inc = client.post(
        f"/mini-wallets/{mini_a}/transactions",
        headers=auth(token_a),
        json={"amount": "500.00", "type": "income", "category": "Gift", "modeofpayment": "bank"},
    ).json()
    tx_a_id = inc["id"]

    # Bob sets up his own wallet
    client.post("/super-wallet", headers=auth(token_b), json={"name": "Bob Super", "currency": "USD"})

    # Bob tries to view Alice's mini-wallet transactions -> 403 Forbidden
    bob_view = client.get(f"/mini-wallets/{mini_a}/transactions", headers=auth(token_b))
    assert bob_view.status_code == 403

    # Bob tries to access Alice's transaction directly -> 403 Forbidden
    bob_tx = client.get(f"/transactions/{tx_a_id}", headers=auth(token_b))
    assert bob_tx.status_code == 403

    # Bob tries to update Alice's transaction -> 403 Forbidden
    bob_upd = client.put(f"/transactions/{tx_a_id}", headers=auth(token_b), json={"amount": "999.00"})
    assert bob_upd.status_code == 403

    # Bob tries to delete Alice's transaction -> 403 Forbidden
    bob_del = client.delete(f"/transactions/{tx_a_id}", headers=auth(token_b))
    assert bob_del.status_code == 403


def test_pagination_and_validation_edge_cases():
    reset_db()
    token = register_and_login("edge_cases@example.com")
    client.post("/super-wallet", headers=auth(token), json={"name": "Super", "currency": "USD"})
    mini_id = client.post("/super-wallet/mini-wallets", headers=auth(token), json={"name": "Mini", "modeofpayment": "cash"}).json()["id"]

    # Pagination limit > 100 should be rejected by FastAPI Query(le=100)
    over_limit = client.get(
        f"/mini-wallets/{mini_id}/transactions?limit=150",
        headers=auth(token),
    )
    assert over_limit.status_code == 422

    # Negative offset should be rejected by Query(ge=0)
    neg_offset = client.get(
        f"/mini-wallets/{mini_id}/transactions?offset=-5",
        headers=auth(token),
    )
    assert neg_offset.status_code == 422

    # Negative amount transaction creation should be rejected
    neg_amt = client.post(
        f"/mini-wallets/{mini_id}/transactions",
        headers=auth(token),
        json={"amount": "-50.00", "type": "income", "category": "General", "modeofpayment": "cash"},
    )
    assert neg_amt.status_code == 422

    # Invalid transaction type
    inv_type = client.post(
        f"/mini-wallets/{mini_id}/transactions",
        headers=auth(token),
        json={"amount": "50.00", "type": "transfer", "category": "General", "modeofpayment": "cash"},
    )
    assert inv_type.status_code == 422
