import asyncio
import os
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

# Ensure test DB
os.environ["DATABASE_URL"] = "sqlite:///./test_wallet_refactor.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["RATE_LIMIT_LOGIN"] = "5/minute"
os.environ["RATE_LIMIT_REGISTER"] = "3/hour"
os.environ["RATE_LIMIT_READ"] = "10/minute"
os.environ["RATE_LIMIT_WRITE"] = "5/minute"
os.environ["RATE_LIMIT_FAIL_OPEN"] = "true"

from app.core import rate_limit
from app.core.rate_limit import get_client_ip, parse_rate_limit
from app.core.redis import close_redis, get_redis_client, init_redis, set_redis_client
from app.main import app
from app.models import Base
from app.services import analytics_service, cache_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_fake_redis():
    """Ensure a clean fake redis instance for every test."""
    fake_r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis_client(fake_r)
    yield fake_r
    set_redis_client(None)


def reset_db():
    from app.database import engine, init_db

    Base.metadata.drop_all(bind=engine)
    init_db()


def create_user(email: str = "redisuser@example.com", name: str = "Redis User") -> str:
    res = client.post(
        "/auth/register",
        json={
            "name": name,
            "phone": str(4000000000 + abs(hash(email)) % 1000000000),
            "email": email,
            "currency": "INR",
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


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_super_wallet(token: str, name: str = "Redis Wallet") -> int:
    res = client.post(
        "/super-wallet",
        headers=auth(token),
        json={"name": name, "currency": "INR"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# =====================================================================
# Feature A & B: Redis Infrastructure & Analytics Caching Tests
# =====================================================================

def test_rate_limit_parser():
    count, window = parse_rate_limit("5/minute")
    assert count == 5 and window == 60

    count, window = parse_rate_limit("3/hour")
    assert count == 3 and window == 3600

    count, window = parse_rate_limit("120/s")
    assert count == 120 and window == 1

    count, window = parse_rate_limit("50 / day")
    assert count == 50 and window == 86400

    with pytest.raises(ValueError):
        parse_rate_limit("invalid")


def test_cache_keys_differ_across_users_and_parameters():
    key1 = cache_service.build_cache_key(1, "daily", date="2026-10-28")
    key2 = cache_service.build_cache_key(2, "daily", date="2026-10-28")
    key3 = cache_service.build_cache_key(1, "daily", date="2026-10-29")
    key_monthly = cache_service.build_cache_key(1, "monthly", year=2026, month=10)

    assert key1 != key2, "Keys must differ across different users"
    assert key1 != key3, "Keys must differ across different date parameters"
    assert "u1" in key1 and "u2" in key2
    assert "daily" in key1 and "monthly" in key_monthly


def test_cache_miss_then_hit_avoids_database_work(setup_fake_redis):
    reset_db()
    token = create_user("cache_test@example.com")
    create_super_wallet(token)

    # 1. First request - Cache Miss: database summary function executes
    with patch.object(
        analytics_service,
        "get_daily_summary",
        wraps=analytics_service.get_daily_summary,
    ) as spy_daily:
        res1 = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
        assert res1.status_code == 200
        assert spy_daily.call_count == 1
        body1 = res1.json()

    # 2. Second request - Cache Hit: database summary function is NOT called
    with patch.object(
        analytics_service,
        "get_daily_summary",
        wraps=analytics_service.get_daily_summary,
    ) as spy_daily:
        res2 = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
        assert res2.status_code == 200
        assert spy_daily.call_count == 0, "Cache hit must avoid executing analytics DB query"
        assert res2.json() == body1


def test_ttl_expiration_recomputes_cache(setup_fake_redis):
    reset_db()
    token = create_user("ttl_test@example.com")
    create_super_wallet(token)

    # Populate cache
    res1 = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
    assert res1.status_code == 200

    # Simulate TTL expiration by deleting keys in fake Redis
    asyncio.run(setup_fake_redis.flushall())

    # After expiration, database calculation should run again
    with patch.object(
        analytics_service,
        "get_daily_summary",
        wraps=analytics_service.get_daily_summary,
    ) as spy_daily:
        res2 = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
        assert res2.status_code == 200
        assert spy_daily.call_count == 1, "After TTL expiration, cache miss must recompute"


def test_cached_data_never_leaks_across_users(setup_fake_redis):
    reset_db()
    token_a = create_user("alice_cache@example.com", "Alice")
    token_b = create_user("bob_cache@example.com", "Bob")
    create_super_wallet(token_a)
    create_super_wallet(token_b)

    # Alice has 1000 income
    client.post(
        "/transactions",
        headers=auth(token_a),
        json={"amount": "1000.00", "type": "income", "category": "Salary", "modeofpayment": "UPI"},
    )
    res_a = client.get("/analytics/daily?date=" + str(date.today()), headers=auth(token_a))
    assert res_a.status_code == 200
    assert res_a.json()["income"] == "1000.00"

    # Bob has 0 income
    res_b = client.get("/analytics/daily?date=" + str(date.today()), headers=auth(token_b))
    assert res_b.status_code == 200
    assert res_b.json()["income"] == "0.00", "Alice's cached income must never leak to Bob"


def test_redis_failure_falls_back_to_postgres(setup_fake_redis):
    reset_db()
    token = create_user("fallback@example.com")
    create_super_wallet(token)

    # Simulate Redis client being completely down (None)
    set_redis_client(None)

    res = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
    assert res.status_code == 200
    assert "income" in res.json()


def test_redis_serialization_error_falls_back_gracefully(setup_fake_redis):
    reset_db()
    token = create_user("serial@example.com")
    create_super_wallet(token)

    # Inject an invalid non-JSON string into Redis for this key
    key = cache_service.build_cache_key(1, "daily", date="2026-10-28")
    asyncio.run(setup_fake_redis.set(key, "{corrupted-not-json!"))

    # Endpoint must gracefully catch JSONDecodeError and calculate from DB without 500 error
    res = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
    assert res.status_code == 200
    assert "income" in res.json()


def test_redis_recovery_restores_caching(setup_fake_redis):
    reset_db()
    token = create_user("recovery@example.com")
    create_super_wallet(token)

    # 1. Outage: Redis unavailable -> falls back to DB
    set_redis_client(None)
    res1 = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
    assert res1.status_code == 200

    # 2. Recovery: Redis comes back online
    set_redis_client(setup_fake_redis)
    # First request populates cache
    res2 = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
    assert res2.status_code == 200

    # Subsequent request is served from recovered cache
    with patch.object(
        analytics_service,
        "get_daily_summary",
        wraps=analytics_service.get_daily_summary,
    ) as spy_daily:
        res3 = client.get("/analytics/daily?date=2026-10-28", headers=auth(token))
        assert res3.status_code == 200
        assert spy_daily.call_count == 0, "Recovered Redis must resume serving from cache"


# =====================================================================
# Feature C: Cache Invalidation Tests
# =====================================================================

def test_transaction_creation_invalidates_cache(setup_fake_redis):
    reset_db()
    token = create_user("inv_create@example.com")
    create_super_wallet(token)
    today = str(date.today())

    # 1. Prime cache: income = 0.00
    res1 = client.get(f"/analytics/daily?date={today}", headers=auth(token))
    assert res1.json()["income"] == "0.00"

    # 2. Add income transaction 500
    create_res = client.post(
        "/transactions",
        headers=auth(token),
        json={"amount": "500.00", "type": "income", "category": "Bonus", "modeofpayment": "CASH"},
    )
    assert create_res.status_code == 201

    # 3. Read daily analytics again: cache must have been invalidated and reflect 500.00
    res2 = client.get(f"/analytics/daily?date={today}", headers=auth(token))
    assert res2.json()["income"] == "500.00"


def test_transaction_update_and_delete_invalidates_cache(setup_fake_redis):
    reset_db()
    token = create_user("inv_upd_del@example.com")
    create_super_wallet(token)
    today = str(date.today())

    # Create transaction 1000
    tx = client.post(
        "/transactions",
        headers=auth(token),
        json={"amount": "1000.00", "type": "income", "category": "Salary", "modeofpayment": "BANK"},
    ).json()

    # Prime cache
    res1 = client.get(f"/analytics/daily?date={today}", headers=auth(token))
    assert res1.json()["income"] == "1000.00"

    # Update amount to 1500
    upd = client.put(
        f"/transactions/{tx['id']}",
        headers=auth(token),
        json={"amount": "1500.00"},
    )
    assert upd.status_code == 200

    # Read analytics: must reflect 1500.00
    res2 = client.get(f"/analytics/daily?date={today}", headers=auth(token))
    assert res2.json()["income"] == "1500.00"

    # Delete transaction
    del_res = client.delete(f"/transactions/{tx['id']}", headers=auth(token))
    assert del_res.status_code == 204

    # Read analytics: must reflect 0.00
    res3 = client.get(f"/analytics/daily?date={today}", headers=auth(token))
    assert res3.json()["income"] == "0.00"


def test_failed_database_transaction_does_not_invalidate_committed_state(setup_fake_redis):
    reset_db()
    token = create_user("fail_tx@example.com")
    create_super_wallet(token)
    today = str(date.today())

    # Prime cache
    client.get(f"/analytics/daily?date={today}", headers=auth(token))

    # Attempt invalid expense exceeding 0 balance
    res = client.post(
        "/transactions",
        headers=auth(token),
        json={"amount": "9999.00", "type": "expense", "category": "Rent", "modeofpayment": "CASH"},
    )
    assert res.status_code == 400


def test_redis_invalidation_failure_does_not_undo_committed_financial_writes(setup_fake_redis):
    reset_db()
    token = create_user("invalidation_err@example.com")
    create_super_wallet(token)

    # Patch invalidate_user_analytics to raise an error
    with patch.object(
        cache_service,
        "invalidate_user_analytics",
        side_effect=Exception("Redis connection exploded"),
    ):
        res = client.post(
            "/transactions",
            headers=auth(token),
            json={"amount": "200.00", "type": "income", "category": "Gift", "modeofpayment": "UPI"},
        )
        # Financial write MUST still succeed and commit!
        assert res.status_code == 201

    # Verify transaction really exists in DB
    tx_list = client.get("/super-wallet/transactions", headers=auth(token)).json()
    assert len(tx_list) == 1
    assert tx_list[0]["amount"] == "200.00"


# =====================================================================
# Feature D: Distributed Rate Limiting Tests
# =====================================================================

def test_login_rate_limiting_blocks_after_limit_and_returns_429(setup_fake_redis):
    reset_db()
    # Configure limit = 3/minute for this test
    with patch.dict(os.environ, {"RATE_LIMIT_LOGIN": "3/minute"}):
        # 3 requests allowed
        for i in range(3):
            res = client.post(
                "/auth/login",
                json={"email": "nobody@example.com", "password": "wrong"},
            )
            assert res.status_code in (401, 200)

        # 4th request must be blocked by rate limiter with 429
        blocked = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "wrong"},
        )
        assert blocked.status_code == 429
        assert "Rate limit exceeded" in blocked.json()["detail"]
        assert "Retry-After" in blocked.headers
        assert int(blocked.headers["Retry-After"]) >= 1


def test_rate_limit_user_isolation(setup_fake_redis):
    reset_db()
    token_a = create_user("limiter_a@example.com", "User A")
    token_b = create_user("limiter_b@example.com", "User B")
    create_super_wallet(token_a)
    create_super_wallet(token_b)

    with patch.dict(os.environ, {"RATE_LIMIT_WRITE": "2/minute"}):
        # User A makes 2 writes (at limit)
        for i in range(2):
            res_a = client.post(
                "/transactions",
                headers=auth(token_a),
                json={"amount": "50.00", "type": "income", "category": "Food", "modeofpayment": "UPI"},
            )
            assert res_a.status_code == 201

        # User A's 3rd request -> 429
        res_a_blocked = client.post(
            "/transactions",
            headers=auth(token_a),
            json={"amount": "50.00", "type": "income", "category": "Food", "modeofpayment": "UPI"},
        )
        assert res_a_blocked.status_code == 429

        # User B should NOT be blocked because limits are isolated per user
        res_b = client.post(
            "/transactions",
            headers=auth(token_b),
            json={"amount": "100.00", "type": "income", "category": "Food", "modeofpayment": "UPI"},
        )
        assert res_b.status_code == 201


def test_invalid_jwt_rejected_before_rate_limit(setup_fake_redis):
    # Invalid token must return 401 Unauthorized, never rate limited
    res = client.get("/analytics/daily", headers={"Authorization": "Bearer invalid_token_123"})
    assert res.status_code == 401


def test_trusted_proxy_ip_resolution():
    req = MagicMock()
    req.client.host = "10.0.0.1"
    req.headers = {"X-Forwarded-For": "203.0.113.195, 10.0.0.1"}

    # Case 1: Untrusted proxy -> ignores X-Forwarded-For
    with patch.dict(os.environ, {"TRUSTED_PROXIES": ""}):
        assert get_client_ip(req) == "10.0.0.1"

    # Case 2: Trusted proxy -> uses client IP from X-Forwarded-For
    with patch.dict(os.environ, {"TRUSTED_PROXIES": "10.0.0.1"}):
        assert get_client_ip(req) == "203.0.113.195"


def test_rate_limit_fail_open_policy(setup_fake_redis):
    reset_db()
    token = create_user("failopen@example.com")
    create_super_wallet(token)

    # When Redis is completely down and fail_open is true:
    set_redis_client(None)
    with patch.dict(os.environ, {"RATE_LIMIT_FAIL_OPEN": "true"}):
        res = client.post(
            "/transactions",
            headers=auth(token),
            json={"amount": "10.00", "type": "income", "category": "Gift", "modeofpayment": "CASH"},
        )
        assert res.status_code == 201


def test_rate_limit_fail_closed_policy(setup_fake_redis):
    reset_db()
    token = create_user("failclosed@example.com")
    create_super_wallet(token)

    # When Redis is down and fail_open is false:
    set_redis_client(None)
    with patch.dict(os.environ, {"RATE_LIMIT_FAIL_OPEN": "false"}):
        res = client.post(
            "/transactions",
            headers=auth(token),
            json={"amount": "10.00", "type": "income", "category": "Gift", "modeofpayment": "CASH"},
        )
        assert res.status_code == 503
        assert "temporarily unavailable" in res.json()["detail"]


# =====================================================================
# Feature E: Health Checks and Resilience Tests
# =====================================================================

def test_health_reports_database_and_redis_separately(setup_fake_redis):
    reset_db()
    # When Redis is up
    res_online = client.get("/health")
    assert res_online.status_code == 200
    data_online = res_online.json()
    assert data_online["status"] == "healthy"
    assert data_online["database"] == "connected"
    assert data_online["redis"] == "connected"

    # When Redis is unavailable
    set_redis_client(None)
    res_offline = client.get("/health")
    assert res_offline.status_code == 200, "API must remain accessible when Redis is down"
    data_offline = res_offline.json()
    assert data_offline["database"] == "connected"
    assert data_offline["redis"] == "unavailable"


def test_health_endpoint_is_exempt_from_rate_limiting(setup_fake_redis):
    # Make multiple health requests rapidly; none should return 429
    for _ in range(20):
        res = client.get("/health")
        assert res.status_code == 200
