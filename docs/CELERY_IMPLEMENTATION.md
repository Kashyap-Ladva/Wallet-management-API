# Celery Distributed Background Task Architecture

This document details the production-ready Celery background task processing and scheduling implementation in the Wallet Management API.

---

## 1. System Architecture

The background processing pipeline follows a distributed architecture designed for high availability, financial data consistency, and horizontal scalability:

```
                      +-------------------+
                      |   FastAPI App     |
                      | (HTTP Endpoints)  |
                      +---------+---------+
                                |
             +------------------+------------------+
             |                                     |
   (Enqueues async tasks)                 (Schedules recurring jobs)
             |                                     |
             v                                     v
+------------------------+             +------------------------+
|      Redis Broker      |             |      Celery Beat       |
|      (Database 1)      |             | (Periodic Job Trigger) |
+------------+-----------+             +------------------------+
             |                                     |
             +------------------+------------------+
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
+-------------------------+           +-------------------------+
|     Celery Worker 1     |           |     Celery Worker N     |
| (Imports, Notifications)|           |  (Summaries, Analytics) |
+------------+------------+           +------------+------------+
             |                                     |
             +------------------+------------------+
                                |
             +------------------+------------------+
             |                                     |
             v                                     v
+------------------------+             +------------------------+
|   PostgreSQL Engine    |             |  Redis Result Backend  |
|  (Source of Truth)     |             |      (Database 2)      |
+------------------------+             +------------------------+
```

### Redis Logical Database Isolation

To prevent message or cache collisions, Redis traffic is strictly partitioned into distinct logical databases:

| Database | Component | Purpose | URL Default |
|---|---|---|---|
| **DB 0** | Cache & Rate Limiting | Analytics caching, Lua sliding-window rate limit counters | `redis://localhost:6379/0` |
| **DB 1** | Celery Message Broker | FIFO task message queues and exchanges | `redis://localhost:6379/1` |
| **DB 2** | Celery Result Backend | Asynchronous task status and primitive result store | `redis://localhost:6379/2` |

> [!IMPORTANT]
> Celery broker and result backend traffic never interfere with or flush the application's caching or rate-limiting state.

---

## 2. Celery Configuration

Configuration resides in `app/core/celery_app.py` and is exported via `app/celery_app.py`.

### Key Parameters:

```python
celery_app.conf.update(
    broker_url=CELERY_BROKER_URL,
    result_backend=CELERY_RESULT_BACKEND,
    # Serialization security
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone & Scheduling
    timezone="UTC",
    enable_utc=True,
    # Worker execution & reliability
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    task_time_limit=600,
    task_soft_time_limit=300,
)
```

- **JSON Serialization Only:** No pickle or untrusted serializations are accepted. Only primitive Python types, dictionaries, and lists are passed.
- **Late Acknowledgements (`task_acks_late=True`):** Tasks are acknowledged only after completion. If a worker process crashes mid-task, the message remains in Redis and is redelivered.
- **Crash Recovery (`task_reject_on_worker_lost=True`):** Rejects and requeues tasks if a worker child process terminates abruptly (e.g., OOM kill).
- **Fair Prefetching (`worker_prefetch_multiplier=1`):** Workers take exactly one unacknowledged message at a time, eliminating queue starvation when long-running Excel imports run alongside lightweight notification jobs.
- **Task Time Limits:** Hard limit of 600s and soft limit of 300s prevent hanging tasks from permanently tying up worker processes.

### Task Routing & Specialized Queues

Tasks are partitioned into dedicated queues for workload isolation:

| Queue | Tasks Routed | Concurrency Strategy |
|---|---|---|
| `imports` | `app.jobs.excel_import.*` | Heavy CPU/IO Excel parsing & validation |
| `scheduled` | `app.jobs.daily_summary.*`, `app.jobs.monthly_reminders.*` | Periodic cron jobs triggered by Celery Beat |
| `notifications` | `app.jobs.notifications.*` | Bulk/single alert and reminder dispatch |
| `default` | `app.jobs.analytics.*` | Background cache warming and general maintenance |

---

## 3. Background Tasks Implemented

### A. Daily Financial Summary (`app.jobs.daily_summary`)
- **Celery Task:** `generate_daily_summaries_task(target_date_str=None)`
- **Schedule:** Daily at `23:59 UTC` (migrated from APScheduler).
- **Per-User Isolation:** Iterates active users and encapsulates each summary in a nested database savepoint (`db.begin_nested()`). An unexpected computation failure for one user logs an error without interrupting summary generation for all other users.
- **Payload:** Calculates daily income, expenses, net balance, category breakdown, mini-wallet breakdown, and checks daily/monthly budget progress.
- **Deduplication:** Enforces `dedupe_key=daily-summary:{target_date.isoformat()}`.

### B. Monthly Recurring Payment Reminders (`app.jobs.monthly_reminders`)
- **Celery Task:** `generate_monthly_reminders_task(target_date_str=None)`
- **Schedule:** Monthly on day 1 at `00:05 UTC` (migrated from APScheduler).
- **Due Date Computation:** Handles month-end date variations (e.g., February 28/29, April 30) using `min(payment.due_day, month_end)`.
- **Deduplication:** Enforces `dedupe_key=recurring-payment:{payment.id}:{YYYY-MM}`.

### C. Asynchronous Excel Transaction Import (`app.jobs.excel_import`)
- **Celery Task:** `process_excel_import_task(import_job_id, super_wallet_id, user_id, file_path, preview_sha256)`
- **Lifecycle Tracking:** Transitions database record `ImportJob` through `PENDING -> PROCESSING -> COMPLETED | FAILED`.
- **Financial Integrity:** 
  1. Verifies SHA-256 digest against previewed digest.
  2. Previews all rows and checks available mini-wallet balances before creating any ledger entries.
  3. All rows are committed within a single atomic database transaction. If any row fails, the entire batch rolls back.
  4. Automatically invalidates the user's cached analytics upon commit.
  5. Cleans up the temporary staged upload file upon completion or failure.
  6. Permanent validation errors are marked `FAILED` immediately and never retried.

### D. Asynchronous Notifications (`app.jobs.notifications`)
- **Celery Tasks:**
  - `dispatch_notification_task(user_id, kind, message, payload, dedupe_key, recurring_payment_id)`
  - `dispatch_bulk_notifications_task(notifications_data)`
- **Guarantees:** Savepoint isolation per item, automatic deduplication check.

### E. Analytics Cache Pre-Warming (`app.jobs.analytics`)
- **Celery Task:** `warm_user_analytics_cache_task(user_id)`
- **Purpose:** Pre-computes daily and monthly dashboard summaries in the background and populates Redis cache without blocking FastAPI request threads.

---

## 4. Financial Integrity & Idempotency Rules

Financial ledger operations must adhere to strict consistency requirements in distributed systems:

1. **No Retries on Business/Validation Failures:**
   Celery tasks configured with `@celery_app.task` specify `autoretry_for=(OperationalError, DBAPIError)`. Transient database connection drops trigger exponential backoff retries, but `ValueError`, balance errors, and schema validation errors fail permanently without retry.
2. **Atomic Ledger Insertion:**
   Celery workers never modify wallet balances in detached steps. All mini-wallet balance adjustments occur via transaction rows inside atomic SQLAlchemy sessions.
3. **Deduplication Keys:**
   Summary and reminder notifications use unique constraints `(user_id, dedupe_key)` in PostgreSQL/SQLite to guarantee exactly-once creation regardless of task re-deliveries.

---

## 5. Database Session Management

Background tasks run in separate OS processes and must never share SQLAlchemy sessions with FastAPI or other worker threads.

### Dedicated Task Session Context Manager (`app.database.get_task_db`)

```python
@contextmanager
def get_task_db() -> Generator[Session, None, None]:
    """
    Dedicated database session generator for background Celery tasks.
    Creates a fresh, isolated session, rolls back on exceptions, and guarantees closure
    to prevent connection leaks in worker processes.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

- **Fresh Session per Task:** Each task execution instantiates a distinct `SessionLocal()`.
- **Automatic Rollback:** Any unhandled exception triggers an immediate `db.rollback()`.
- **Guaranteed Cleanup:** `finally: db.close()` returns the connection to the engine pool, preventing connection leaks.

---

## 6. API Integration & Security

### Endpoints Added:

| Method | Endpoint | Status | Description |
|---|---|---|---|
| `POST` | `/imports/async` | `202 Accepted` | Submit an Excel workbook for background processing |
| `POST` | `/imports/excel/async` | `202 Accepted` | Alias for `/imports/async` |
| `GET` | `/imports/{import_id}/status` | `200 OK` | Inspect async import status, progress, row count, errors |
| `GET` | `/tasks/{task_id}` | `200 OK` | Check generic Celery task status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`, `RETRY`) |

### Strict User Ownership & Authorization:
- When a task is queued, its ownership is mapped to `current_user.id` in `ImportJob` and Redis.
- Querying `/imports/{import_id}/status` or `/tasks/{task_id}` strictly verifies that `job.user_id == current_user.id`.
- Access attempts by unauthorized users return `403 Forbidden`.
- Unknown IDs return `404 Not Found`.
- Internal stack traces or raw exceptions are never exposed to the client.

---

## 7. Celery Beat Scheduling Migration

Scheduling responsibility has been completely migrated out of FastAPI lifespan into standalone **Celery Beat**:

- **Previous Implementation:** Embedded `APScheduler` inside FastAPI `lifespan`. This caused duplicated scheduled jobs when running multiple API worker processes (e.g. under Gunicorn/Uvicorn multi-worker mode).
- **Current Implementation:** Celery Beat runs as a dedicated singleton process or container. It dispatches scheduled task messages to the Redis broker at configured cron intervals. Celery workers pick up and execute the jobs.
- **Timezone:** Standardized on `UTC`.

---

## 8. Worker Scaling & Production Operations

### Running Locally

```powershell
# 1. Start Celery Worker (all queues)
celery -A app.celery_app.celery_app worker --loglevel=INFO -c 4 -Q default,imports,scheduled,notifications

# 2. Start Celery Beat (scheduler)
celery -A app.celery_app.celery_app beat --loglevel=INFO

# 3. Optional: Start Flower monitoring dashboard
celery -A app.celery_app.celery_app flower --port=5555 --basic_auth=admin:admin123!
```

### Running with Docker Compose

```powershell
# Start complete stack: db, redis, api, celery_worker, celery_beat, flower
docker compose up -d --build

# View worker logs
docker compose logs -f celery_worker

# View beat logs
docker compose logs -f celery_beat
```

### Production Checklist:
- Set secure `SECRET_KEY` and `FLOWER_BASIC_AUTH`.
- Ensure persistent storage is mounted at `/app/data` for staged imports and proofs.
- Scale workers independently: `docker compose up -d --scale celery_worker=3`.
- Dedicated worker nodes can subscribe specifically to heavy queues: `celery worker -Q imports -c 2`.

