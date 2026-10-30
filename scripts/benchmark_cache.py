import asyncio
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fakeredis.aioredis
from fastapi.testclient import TestClient

# Setup test environment
os.environ["DATABASE_URL"] = "sqlite:///./test_benchmark.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["RATE_LIMIT_READ"] = "10000/minute"
os.environ["RATE_LIMIT_WRITE"] = "10000/minute"

from app.core.redis import set_redis_client
from app.database import engine, init_db
from app.main import app
from app.models import Base

client = TestClient(app)


def setup_benchmark_data():
    Base.metadata.drop_all(bind=engine)
    init_db()

    # Create user
    res = client.post(
        "/auth/register",
        json={
            "name": "Benchmark User",
            "phone": "9876543210",
            "email": "bench@example.com",
            "currency": "INR",
            "password": "Password123!",
        },
    )
    login = client.post(
        "/auth/login",
        json={"email": "bench@example.com", "password": "Password123!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/super-wallet",
        headers=headers,
        json={"name": "Benchmark Wallet", "currency": "INR"},
    )

    # Insert 50 transactions across categories
    categories = ["Food", "Transport", "Salary", "Utilities", "Entertainment", "Shopping"]
    modes = ["UPI", "CASH", "CARD", "BANK"]
    for i in range(50):
        ttype = "income" if i % 4 == 0 else "expense"
        client.post(
            "/transactions",
            headers=headers,
            json={
                "amount": f"{(i + 1) * 10}.00",
                "type": ttype,
                "category": categories[i % len(categories)],
                "modeofpayment": modes[i % len(modes)],
            },
        )

    return headers


def run_benchmark(num_requests: int = 100, concurrency: int = 5):
    print("=" * 70)
    print("      WALLET MANAGEMENT API - ANALYTICS CACHE PERFORMANCE BENCHMARK")
    print("=" * 70)

    headers = setup_benchmark_data()
    endpoint = "/analytics/daily"

    # --- Phase 1: Cold / Uncached (Database Aggregation Query) ---
    print(f"\n[1] Running {num_requests} requests WITHOUT cache (simulated cold miss / direct DB)...")
    cold_latencies = []

    for _ in range(num_requests):
        # Disable cache client to force database execution
        set_redis_client(None)
        t0 = time.perf_counter()
        res = client.get(endpoint, headers=headers)
        t1 = time.perf_counter()
        assert res.status_code == 200
        cold_latencies.append((t1 - t0) * 1000)

    # --- Phase 2: Warm Cache (Redis Hit) ---
    fake_r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis_client(fake_r)

    # Prime the cache once
    res_prime = client.get(endpoint, headers=headers)
    assert res_prime.status_code == 200

    print(f"[2] Running {num_requests} requests WITH warm Redis cache...")
    warm_latencies = []

    for _ in range(num_requests):
        t0 = time.perf_counter()
        res = client.get(endpoint, headers=headers)
        t1 = time.perf_counter()
        assert res.status_code == 200
        warm_latencies.append((t1 - t0) * 1000)

    # --- Phase 3: Concurrent Benchmark (Warm Cache) ---
    print(f"[3] Running {num_requests} requests under {concurrency} concurrent threads...")
    concurrent_latencies = []

    def make_req(_):
        t0 = time.perf_counter()
        r = client.get(endpoint, headers=headers)
        t1 = time.perf_counter()
        assert r.status_code == 200
        return (t1 - t0) * 1000

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        concurrent_latencies = list(executor.map(make_req, range(num_requests)))

    # Compute Statistics
    cold_sorted = sorted(cold_latencies)
    warm_sorted = sorted(warm_latencies)
    conc_sorted = sorted(concurrent_latencies)

    def stats(data):
        return {
            "avg": statistics.mean(data),
            "p50": statistics.median(data),
            "p95": data[int(len(data) * 0.95)],
            "min": min(data),
            "max": max(data),
        }

    s_cold = stats(cold_sorted)
    s_warm = stats(warm_sorted)
    s_conc = stats(conc_sorted)

    speedup_avg = (s_cold["avg"] - s_warm["avg"]) / s_cold["avg"] * 100
    speedup_p50 = (s_cold["p50"] - s_warm["p50"]) / s_cold["p50"] * 100
    speedup_p95 = (s_cold["p95"] - s_warm["p95"]) / s_cold["p95"] * 100

    print("\n" + "=" * 70)
    print("                        BENCHMARK RESULTS")
    print("=" * 70)
    print(f"{'Metric':<18} | {'Direct DB (ms)':<16} | {'Redis Hit (ms)':<16} | {'Speedup':<10}")
    print("-" * 70)
    print(f"{'Average Latency':<18} | {s_cold['avg']:>13.2f} ms | {s_warm['avg']:>13.2f} ms | {speedup_avg:>8.1f}%")
    print(f"{'p50 Latency':<18} | {s_cold['p50']:>13.2f} ms | {s_warm['p50']:>13.2f} ms | {speedup_p50:>8.1f}%")
    print(f"{'p95 Latency':<18} | {s_cold['p95']:>13.2f} ms | {s_warm['p95']:>13.2f} ms | {speedup_p95:>8.1f}%")
    print(f"{'Min Latency':<18} | {s_cold['min']:>13.2f} ms | {s_warm['min']:>13.2f} ms | {'-':>9}")
    print(f"{'Max Latency':<18} | {s_cold['max']:>13.2f} ms | {s_warm['max']:>13.2f} ms | {'-':>9}")
    print("-" * 70)
    print(f"Concurrent ({concurrency} threads): avg={s_conc['avg']:.2f}ms, p50={s_conc['p50']:.2f}ms, p95={s_conc['p95']:.2f}ms")
    print(f"Error Rate: 0.0% (all {num_requests * 3} requests returned 200 OK)")
    print("=" * 70)

    # Cleanup test DB
    try:
        os.remove("test_benchmark.db")
    except OSError:
        pass


if __name__ == "__main__":
    run_benchmark(num_requests=100, concurrency=5)
