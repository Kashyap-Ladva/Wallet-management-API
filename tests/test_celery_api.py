from datetime import date
from decimal import Decimal
from io import BytesIO
import os
from unittest.mock import patch

import fakeredis.aioredis
from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_celery_api.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["RATE_LIMIT_LOGIN"] = "50/minute"
os.environ["RATE_LIMIT_REGISTER"] = "50/hour"
os.environ["RATE_LIMIT_READ"] = "120/minute"
os.environ["RATE_LIMIT_WRITE"] = "50/minute"
os.environ["RATE_LIMIT_FAIL_OPEN"] = "true"

from app.core.celery_app import celery_app
from app.core.redis import set_redis_client
from app.database import engine, init_db
from app.main import app
from app.models import Base

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_api_env():
    orig_backend = celery_app.conf.result_backend
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        result_backend="cache+memory://",
    )
    fake_r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis_client(fake_r)
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield fake_r
    set_redis_client(None)
    celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
        result_backend=orig_backend,
    )


def _register_and_login(email: str, name: str = "Test User") -> tuple[str, int]:
    reg = client.post(
        "/auth/register",
        json={
            "name": name,
            "phone": str(5000000000 + abs(hash(email)) % 1000000000),
            "email": email,
            "currency": "INR",
            "password": "Password123!",
        },
    )
    assert reg.status_code == 201, reg.text
    user_id = reg.json()["id"]

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"], user_id


def _setup_wallet(token: str) -> int:
    client.post(
        "/super-wallet",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Primary Super Wallet", "currency": "INR"},
    )
    mini = client.post(
        "/super-wallet/mini-wallets",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Bank Account", "modeofpayment": "bank"},
    )
    assert mini.status_code == 201, mini.text
    return mini.json()["id"]


def _workbook_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["amount", "type", "category", "date_created", "modeofpayment", "description", "proof"])
    for row in rows:
        ws.append(row)
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_async_import_flow_returns_202_accepted():
    token, user_id = _register_and_login("async_api_1@example.com")
    mini_id = _setup_wallet(token)

    content = _workbook_bytes(
        [
            [2000, "income", "salary", date(2026, 11, 1), "bank", "Stipend", None],
            [500, "expense", "food", date(2026, 11, 2), "bank", "Groceries", None],
        ]
    )

    # Submit asynchronous import
    res = client.post(
        "/imports/async",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("transactions.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res.status_code == 202, res.text
    body = res.json()
    assert "import_id" in body
    assert "task_id" in body
    assert body["status"] == "PENDING"
    assert "file_sha256" in body

    import_id = body["import_id"]
    task_id = body["task_id"]

    # Poll import status
    status_res = client.get(
        f"/imports/{import_id}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_res.status_code == 200
    status_body = status_res.json()
    assert status_body["import_id"] == import_id
    assert status_body["status"] in ("PENDING", "PROCESSING", "COMPLETED")
    assert status_body["total_rows"] == 2
    assert status_body["imported_count"] == 2

    # Poll generic task status
    task_res = client.get(
        f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert task_res.status_code == 200
    task_body = task_res.json()
    assert task_body["task_id"] == task_id
    assert task_body["status"] in ("PENDING", "PROCESSING", "COMPLETED")


def test_cross_user_isolation_on_imports_and_tasks():
    token_a, user_a = _register_and_login("user_a@example.com", "User A")
    token_b, user_b = _register_and_login("user_b@example.com", "User B")
    _setup_wallet(token_a)
    _setup_wallet(token_b)

    content = _workbook_bytes(
        [[1000, "income", "gift", date(2026, 11, 1), "bank", "Bonus", None]]
    )

    # User A creates async import
    res_a = client.post(
        "/imports/async",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("transactions.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res_a.status_code == 202
    import_id = res_a.json()["import_id"]
    task_id = res_a.json()["task_id"]

    # User B attempts to access User A's import status -> 403 Forbidden
    forbidden_import = client.get(
        f"/imports/{import_id}/status",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden_import.status_code == 403
    assert forbidden_import.json()["detail"] == "Forbidden"

    # User B attempts to access User A's task status -> 403 Forbidden
    forbidden_task = client.get(
        f"/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden_task.status_code == 403
    assert forbidden_task.json()["detail"] == "Forbidden"


def test_unknown_task_and_import_ids_return_404():
    token, _ = _register_and_login("unknown_ids@example.com")

    # Non-existent import id
    bad_import = client.get(
        "/imports/non-existent-import-uuid/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_import.status_code == 404
    assert bad_import.json()["detail"] == "Import job not found"

    # Non-existent task id
    bad_task = client.get(
        "/tasks/non-existent-task-uuid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_task.status_code == 404
    assert bad_task.json()["detail"] == "Task not found"


def test_unauthenticated_requests_are_rejected():
    # Unauthenticated import status
    assert client.get("/imports/any-id/status").status_code == 401

    # Unauthenticated task status
    assert client.get("/tasks/any-id").status_code == 401

    # Unauthenticated async import submission
    content = _workbook_bytes([[100, "income", "misc", date(2026, 11, 1), "bank", "Test", None]])
    assert client.post(
        "/imports/async",
        files={"file": ("test.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).status_code == 401
