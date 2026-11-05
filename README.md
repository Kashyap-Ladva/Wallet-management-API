# Wallet Management API

A FastAPI backend for managing user wallets, income and expense transactions, budgets, financial goals, and recurring-payment reminders. It uses SQLAlchemy for persistence and PostgreSQL in production.

## Features

- JWT bearer authentication and user-scoped API access
- One super wallet per user, containing general wallet details (name, currency, owner) without a mode of payment
- Automatic mini-wallet resolution per mode of payment (CASH, CARD, UPI, BANK TRANSFER, etc.) under each super-wallet
- Unique constraint enforcing exactly one mini-wallet per normalized mode of payment per super-wallet
- Direct transaction recording via `/transactions` or `/super-wallet/transactions` with automatic mini-wallet resolution and reuse
- Income and expense transactions with balances derived from transaction history
- Transaction filtering, pagination, and text/image proof references
- Daily, monthly, and yearly analytics, category breakdowns, and chart data with Redis caching
- Redis caching for analytics endpoints (cache-aside, deterministic user-scoped keys, configurable TTLs, and resilient fallback)
- Safe, user-scoped cache invalidation upon financial writes (transactions create, update, delete, Excel import)
- Redis-backed distributed rate limiting (atomic sliding-window Lua script for login, register, read, and write endpoints)
- Daily and monthly budgets with status checks
- Excel transaction preview, per-row mini-wallet resolution, validation, and atomic import
- Savings goals, contributions, withdrawals, and progress
- Separate investment records
- Lent/borrowed debt tracking and repayment history
- Monthly recurring payments
- Scheduled daily summaries and monthly reminder notifications

## Technology

- Python 3.10+
- FastAPI, Pydantic, SQLAlchemy 2.0
- PostgreSQL (via psycopg)
- Celery 5.4+ with Redis for asynchronous background tasks and distributed task processing
- Celery Beat for timezone-aware scheduled recurring jobs (replacing in-process APScheduler)
- Flower for real-time task and worker observability and monitoring
- Redis for analytics caching, distributed sliding-window rate limiting, and Celery broker/backend
- openpyxl for `.xlsx` imports

## Project structure

```text
app/
├── core/
│   ├── auth.py             # JWT bearer authentication and password hashing
│   ├── celery_app.py       # Celery instance, Redis DB isolation, routing, beat schedule & signals
│   ├── config.py           # Settings management via pydantic-settings
│   ├── dependencies.py     # FastAPI dependency injection (DB sessions, current user, rate limiting)
│   ├── logging.py          # Structured application logging
│   ├── rate_limit.py       # Redis-backed sliding-window distributed rate limiter
│   └── security.py         # Security headers and request ID tracing middleware
├── jobs/
│   ├── __init__.py         # Celery task package exports
│   ├── analytics.py        # Analytics cache warming background tasks
│   ├── daily_summary.py    # Daily financial summary generation Celery task & engine
│   ├── excel_import.py     # Asynchronous Excel transaction import worker task
│   ├── monthly_reminders.py# Monthly recurring payment reminder Celery task & engine
│   └── notifications.py    # Asynchronous notification dispatch worker tasks
├── routers/
│   ├── analytics.py        # Analytics endpoints with Redis cache-aside
│   ├── auth.py             # User registration and login endpoints
│   ├── budgets.py          # Budget creation, tracking, and status
│   ├── debts.py            # Debt management and repayments
│   ├── imports.py          # Synchronous and asynchronous Excel imports
│   ├── investments.py      # Investment tracking
│   ├── mini_wallets.py     # Mini-wallet management per payment mode
│   ├── notifications.py    # User notification querying and read status
│   ├── recurring_payments.py # Recurring payment schedules
│   ├── savings.py          # Savings goals, deposits, and withdrawals
│   ├── super_wallets.py    # Super-wallet management and aggregations
│   ├── tasks.py            # Background task status polling (authenticated)
│   └── transactions.py     # Direct transaction recording with mini-wallet auto-resolution
├── schema/
│   ├── celery_tasks.py     # Pydantic schemas for Celery task and async import responses
│   └── ...                 # Domain request/response Pydantic schemas
├── services/               # Core business logic and database transaction operations
├── celery_app.py           # Celery application entrypoint for CLI & worker runners
├── database.py             # SQLAlchemy engine, get_db() FastAPI dependency & get_task_db() task context
├── main.py                 # FastAPI application, CORS, lifespan, and router mounting
└── models.py               # SQLAlchemy models (User, Wallet, Transaction, ImportJob, etc.)
docs/
└── CELERY_IMPLEMENTATION.md # In-depth Celery architectural and production specification
tests/                      # Comprehensive automated test suite (Pytest)
```

## Setup

### 1. Create and activate a virtual environment

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Environment configuration

Copy the template configuration file:

```powershell
cp .env.example .env
```

Set the following environment variables in `.env`:

```dotenv
# Database Configuration
DATABASE_URL=postgresql+psycopg://wallet_user:your-password@localhost:5432/wallet_management

# Security & Authentication
SECRET_KEY=replace-with-a-secure-random-secret-key-32-chars-minimum
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# Redis Caching & Rate Limiting (Logical DB 0)
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_FAIL_OPEN=true

# Celery Broker & Result Backend (Logical DB 1 & DB 2)
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TASK_TIME_LIMIT=600
CELERY_TASK_SOFT_TIME_LIMIT=540
CELERY_RESULT_EXPIRES=86400
CELERY_WORKER_CONCURRENCY=4

# Flower Monitoring Dashboard
FLOWER_PORT=5555
FLOWER_BASIC_AUTH=admin:walletadmin123

# Logging Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Storage Directories
FILE_STORAGE_PATH=app/data
IMPORT_STORAGE_PATH=app/data/imports
```

`DATABASE_URL` is required. `SECRET_KEY` should be set to a private random value in every non-test environment. Logical Redis databases are strictly partitioned: DB 0 for caching/rate limiting, DB 1 for Celery broker messages, and DB 2 for task results.

### Storage paths

- **Proof image storage:** Transaction proof images are stored locally under `FILE_STORAGE_PATH` (defaults to `app/data/proofs`). Uploads are verified via MIME-type and magic-byte signatures (JPEG, PNG, GIF, WebP) with a 5 MB maximum size limit.
- **Asynchronous import staging:** Excel files submitted via `POST /imports/async` are staged in `IMPORT_STORAGE_PATH` (defaults to `app/data/imports`) and processed asynchronously by the Celery worker before automatic cleanup.

## Run Locally

Ensure PostgreSQL and Redis are running locally before starting the services.

### 1. Start the FastAPI API Server

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The API is available at:
- API root: <http://127.0.0.1:8000/>
- Health check (includes database status): <http://127.0.0.1:8000/health>
- Swagger UI documentation: <http://127.0.0.1:8000/docs>
- ReDoc documentation: <http://127.0.0.1:8000/redoc>

### 2. Start the Celery Worker

In a separate terminal with virtual environment activated:

On Linux / macOS / Docker:
```bash
celery -A app.celery_app.celery_app worker --loglevel=INFO -Q imports,scheduled,notifications,default -c 4
```

On Windows (using solo execution pool to prevent Win32 subprocess issues):
```powershell
celery -A app.celery_app.celery_app worker --pool=solo --loglevel=INFO -Q imports,scheduled,notifications,default
```

### 3. Start the Celery Beat Scheduler

In a separate terminal to run periodic scheduled jobs (daily financial summaries at 23:59 UTC, monthly payment reminders on the 1st at 00:05 UTC):

```powershell
celery -A app.celery_app.celery_app beat --loglevel=INFO
```

### 4. Start the Flower Monitoring Dashboard (Optional)

```powershell
celery -A app.celery_app.celery_app flower --port=5555 --basic_auth=admin:walletadmin123
```
Access the real-time Celery dashboard at: <http://127.0.0.1:5555/>

## Run with Docker Compose

To launch the complete production-ready stack in Docker containers (PostgreSQL 16, Redis 7, FastAPI API, Celery Worker, Celery Beat, and Flower):

```powershell
# Build images and start all services in the background
docker compose up --build -d
```

### Monitor Services

```powershell
# Follow logs for all services
docker compose logs -f

# Follow logs specifically for the Celery worker and scheduler
docker compose logs -f celery_worker celery_beat

# Check container health and status
docker compose ps
```

### Scale Celery Workers

```powershell
# Scale worker pool dynamically to 3 worker containers
docker compose up -d --scale celery_worker=3
```

### Stop Services

```powershell
# Stop services and preserve volume data
docker compose down

# Stop services and remove named volumes
docker compose down -v
```

## Security & Observability

- **Request Tracing:** The `SecurityAndObservabilityMiddleware` injects an `X-Request-ID` response header (or propagates an incoming `X-Request-ID`), measures execution latency in milliseconds, and logs structured access logs.
- **Security Headers:** Every response automatically includes `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`.
- **Global Error Handling:** Unhandled exceptions return a standardized JSON response (`{"detail": "Internal server error", "request_id": "..."}`) with status code 500, preventing server leaks.
- **Health Check:** `GET /health` executes a live database ping (`SELECT 1`) and reports connection and scheduler status.

## API endpoints

All endpoints require bearer authentication except registration, login, the root endpoint, and the health check. Wallet, transaction, savings, investment, debt, recurring-payment, and notification operations are strictly restricted to the authenticated user's records.

### System & Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API status message |
| `GET` | `/health` | Live system and database health check |

### Users and wallets

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a user (enforces min 8-character password) |
| `POST` | `/auth/login` | Get a JWT access token |
| `GET` | `/users/me` | Get current user profile |
| `PUT` | `/users/me` | Update current user profile |
| `POST` | `/super-wallet` | Create the user's super wallet (enforces 1 per user) |
| `GET` | `/super-wallet` | Get the user's super wallet |
| `PUT` | `/super-wallet` | Update the user's super wallet |
| `POST` | `/super-wallet/mini-wallets` | Create a mini wallet |
| `GET` | `/super-wallet/mini-wallets` | List mini wallets |
| `GET` | `/mini-wallets/{mini_wallet_id}` | Get a mini wallet |
| `PUT` | `/mini-wallets/{mini_wallet_id}` | Update a mini wallet |
| `DELETE` | `/mini-wallets/{mini_wallet_id}` | Delete a mini wallet |
| `GET` | `/mini-wallets/{mini_wallet_id}/balance` | Get a mini-wallet balance |
| `GET` | `/super-wallet/balance` | Get the super-wallet balance |

### Transactions

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/transactions` | Create an income or expense under user's super-wallet with automatic mini-wallet resolution |
| `POST` | `/super-wallet/transactions` | Create an income or expense under user's super-wallet with automatic mini-wallet resolution |
| `POST` | `/mini-wallets/{mini_wallet_id}/transactions` | Create an income or expense (resolves to mode-of-payment mini-wallet) |
| `GET` | `/mini-wallets/{mini_wallet_id}/transactions` | List mini-wallet transactions (paginated, max limit 100) |
| `GET` | `/super-wallet/transactions` | List super-wallet transactions (paginated, max limit 100) |
| `GET` | `/transactions/{transaction_id}` | Get a transaction |
| `PUT` | `/transactions/{transaction_id}` | Update a transaction (reverses previous financial effect and remaps mini-wallet if mode changes) |
| `DELETE` | `/transactions/{transaction_id}` | Delete a transaction (restores financial balance) |
| `POST` | `/transactions/{transaction_id}/proof` | Attach text or image proof (validated magic bytes, 5 MB limit) |
| `GET` | `/transactions/{transaction_id}/proof` | Retrieve transaction proof image or text |

### Analytics and budgets

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/analytics/daily?date=YYYY-MM-DD` | Daily totals, category breakdown, mini-wallet breakdown |
| `GET` | `/analytics/monthly?year=YYYY&month=MM` | Monthly totals and breakdowns |
| `GET` | `/analytics/yearly?year=YYYY` | Monthly totals for a year |
| `GET` | `/analytics/mini-wallets` | Compare mini-wallet totals |
| `GET` | `/analytics/categories` | Expense totals by category |
| `GET` | `/analytics/expenses/pie` | Pie-chart labels and values |
| `GET` | `/analytics/expenses/bar?year=YYYY` | Bar-chart labels and values |
| `POST` | `/budgets` | Create a daily or monthly budget |
| `GET` | `/budgets` | List budgets |
| `PUT` | `/budgets/{budget_id}` | Update a budget |
| `DELETE` | `/budgets/{budget_id}` | Delete a budget |
| `GET` | `/budgets/{budget_id}/status` | Get budget spending status |

### Imports

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/imports/excel/preview` | Validate and preview rows with per-row mini-wallet resolution and balance check |
| `POST` | `/imports/excel/confirm` | Confirm import using `preview_sha256`; resolves mini-wallets atomically |
| `POST` | `/imports/excel` | Validate and import workbook in one atomic batch (synchronous) |
| `POST` | `/imports/async` | Upload Excel workbook for asynchronous Celery worker processing; returns HTTP 202 with `job_id` and `task_id` |
| `POST` | `/imports/excel/async` | Alias endpoint for asynchronous Excel import processing |
| `GET` | `/imports/{import_id}/status` | Query asynchronous import progress (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`), imported count, and errors |

### Background tasks

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/tasks/{task_id}` | Query Celery task execution status (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`) with strict user ownership enforcement and sanitized state mapping |

### Savings, investments, debt, and recurring payments

| Method | Endpoint | Description |
|---|---|---|
| `POST` / `GET` | `/savings` | Create and list savings goals |
| `PUT` / `DELETE` | `/savings/{goal_id}` | Update or delete a savings goal |
| `POST` | `/savings/{goal_id}/contributions` | Add or withdraw savings (cannot withdraw more than saved) |
| `POST` / `GET` | `/investments` | Create and list investment records |
| `GET` / `PUT` / `DELETE` | `/investments/{investment_id}` | Get, update, or delete an investment |
| `POST` / `GET` | `/debts` | Create and list lent or borrowed records |
| `PUT` / `DELETE` | `/debts/{debt_id}` | Update or delete a debt |
| `POST` | `/debts/{debt_id}/repayments` | Record a repayment (atomic check against remaining amount) |
| `POST` / `GET` | `/recurring-payments` | Create and list recurring payments |
| `PUT` / `DELETE` | `/recurring-payments/{payment_id}` | Update or delete a recurring payment |

### Notifications and scheduled jobs

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/notifications` | List notifications; supports `unread_only`, `limit`, and `offset` |
| `POST` | `/notifications/{notification_id}/read` | Mark a notification as read |

## Redis Caching & Distributed Rate Limiting

### 1. Redis Caching Architecture
- **Cache-Aside Pattern:** Analytics endpoints first check Redis for precomputed responses. On a cache hit, the response is returned immediately without executing heavy database aggregation queries. On a cache miss, data is queried from PostgreSQL/SQLite, serialized, stored in Redis with a configurable TTL, and returned to the client.
- **Deterministic Key Generation:** Cache keys are strictly namespaced, versioned, and isolated by user ID and deterministic query parameters:
  `analytics:v{CACHE_VERSION}:u{user_id}:{endpoint}:{sorted_query_parameters}`
  Example: `analytics:v1:u42:daily:date=2026-10-28`
- **Configurable TTLs:**
  - `ANALYTICS_DAILY_CACHE_TTL`: Default `60` seconds.
  - `ANALYTICS_MONTHLY_CACHE_TTL`: Default `300` seconds.
  - `ANALYTICS_DEFAULT_CACHE_TTL`: Default `120` seconds.
- **Resilience & Fallback:** If Redis is down, times out, or encounters a serialization error, the request gracefully falls back to the database without throwing a 500 error or interrupting user requests.
- **PostgreSQL Source of Truth:** Balances and financial ledger records remain strictly in PostgreSQL/SQLite and are never cached in Redis.

### 2. Cache Invalidation Strategy
- **Transaction Boundaries:** Invalidation occurs only after financial mutations (`create`, `update`, `delete`, and `Excel import`) have successfully committed to the database (`db.commit()`).
- **User-Scoped Invalidation:** Invalidation selectively clears only the affected user's cached analytics (`analytics:*:u{user_id}:*`) using non-blocking scans. No dangerous global flushes (`FLUSHALL` / `FLUSHDB`) are ever executed.
- **Both Old & New Periods Invalidated:** Because invalidation is user-scoped, modifying transaction dates or categories invalidates all affected dashboard aggregations (both previous and new periods).
- **Fault-Tolerant Invalidation:** Invalidation failures are logged as warnings and rely on short TTLs. Invalidation failures never roll back successfully committed financial transactions.

### 3. Distributed Rate Limiting
- **Atomic Lua Sliding Window:** Uses an atomic Redis Lua script executing sliding-window timestamp tracking via sorted sets (`ZSET`). This prevents race conditions and eliminates boundary bursts across multiple worker processes.
- **Protected Endpoint Categories:**
  - **Login:** `5 requests per minute` per client IP (`RATE_LIMIT_LOGIN`). Evaluated before password verification.
  - **Registration:** `3 requests per hour` per client IP (`RATE_LIMIT_REGISTER`). Evaluated before database lookups.
  - **Authenticated Read Endpoints:** `120 requests per minute` per user (`RATE_LIMIT_READ`).
  - **Financial Write Endpoints:** `30 requests per minute` per user (`RATE_LIMIT_WRITE`).
- **Trusted Proxy Resolution:** Client IP extraction strictly evaluates `X-Forwarded-For` only when the direct connection IP matches configured `TRUSTED_PROXIES`.
- **429 Response & Headers:** Exceeding the rate limit immediately returns HTTP `429 Too Many Requests` with a descriptive message and the `Retry-After: <seconds>` response header.
- **Failure Policy (`RATE_LIMIT_FAIL_OPEN`):**
  - `RATE_LIMIT_FAIL_OPEN=true` (default): If Redis is unavailable, rate limiting logs an error and allows requests through so that transient cache outages do not take down core API operations.
  - `RATE_LIMIT_FAIL_OPEN=false`: If Redis is unavailable, requests return HTTP `503 Service Unavailable` to maintain strict rate limits at the cost of service availability during outages.
- **Health Exemption:** `/health` and `/ready` endpoints are completely exempt from rate limiting.

### 4. Performance Verification & Benchmark
A repeatable performance benchmark script is included at `scripts/benchmark_cache.py`:
```powershell
python scripts/benchmark_cache.py
```
**Results over 300 test runs:**
- **Average Latency:** 10.01 ms (Direct DB) vs 5.91 ms (Redis Hit) — **41.0% speedup**
- **p50 Latency:** 7.95 ms (Direct DB) vs 5.52 ms (Redis Hit) — **30.5% speedup**
- **p95 Latency:** 26.15 ms (Direct DB) vs 6.77 ms (Redis Hit) — **74.1% speedup**
- **Error Rate:** 0.0%

## Celery Background Task Processing & Scheduling

The Wallet Management API integrates **Celery 5.4+** with **Redis** to offload long-running operations and periodic workflows from synchronous FastAPI request handling to an asynchronous, distributed worker cluster.

For complete architectural details, lifecycle diagrams, and configuration parameters, see the [Celery Implementation Documentation](file:///d:/Wallet-management-API/docs/CELERY_IMPLEMENTATION.md).

### 1. Architecture Overview

```
                      +--------------------------------------------+
                      |               FastAPI HTTP                 |
                      | (Async Endpoints: /imports/async, etc.)    |
                      +---------------------+----------------------+
                                            |
                         Publishes Task     | Queries Status / Health
                                            v
                      +---------------------+----------------------+
                      |                Redis                       |
                      |  DB 0: Analytics Cache & Rate Limiter      |
                      |  DB 1: Celery Message Broker               |
                      |  DB 2: Celery Result Backend               |
                      +----------+--------------------+------------+
                                 |                    ^
                 Consumes Tasks  |                    | Stores Task Results
                                 v                    |
                      +----------+--------------------+------------+
                      |            Celery Workers                  |
                      |  (Concurrently processes queues:           |
                      |   imports, scheduled, notifications, def)  |
                      +---------------------+----------------------+
                                            |
                       Atomic ACID Sessions | get_task_db()
                                            v
                      +--------------------------------------------+
                      |         PostgreSQL Database                |
                      |     (Authoritative Financial Ledger)       |
                      +---------------------+----------------------+
                                            ^
                       Schedules Crons      |
                                            |
                      +---------------------+----------------------+
                      |             Celery Beat                    |
                      | (Daily Summaries & Monthly Reminders)      |
                      +--------------------------------------------+
```

### 2. Logical Redis Database Isolation

The existing Redis container is leveraged across all caching, rate limiting, and messaging responsibilities with strict logical database isolation to prevent cross-traffic interference, cache flushes, or data contamination:

| Logical DB | Purpose | Access Pattern | Persistence / Eviction |
|---|---|---|---|
| **DB 0** (`REDIS_URL`) | Analytics cache & sliding-window rate limiting | `cache_service.py`, `rate_limit.py` | Volatile / LRU eviction |
| **DB 1** (`CELERY_BROKER_URL`) | Celery message broker queues (`imports`, `scheduled`, etc.) | Celery worker & Beat | Reliable queue storage |
| **DB 2** (`CELERY_RESULT_BACKEND`) | Celery task execution results and state metadata | Celery worker & API status polling | Configurable TTL (`86400s` / 24h) |

### 3. Background Tasks Implemented

#### A. Daily Financial Summary (`generate_daily_summaries_task`)
- **Trigger:** Celery Beat schedule (Daily at 23:59 UTC) or on-demand per user (`generate_user_daily_summary_task`).
- **Functionality:** Computes daily income, expense, net balance, category breakdown, mini-wallet breakdown, and budget spending status across all active users.
- **Savepoint Isolation:** Each user's summary calculation runs inside an isolated sub-transaction (`db.begin_nested()`). A failure for one user logs an error and rolls back only that user's record without interrupting summary generation for all remaining users.
- **Idempotency:** Checks for existing summary records on the target date before generating to prevent duplicate notifications.

#### B. Monthly Recurring Payment Reminders (`generate_monthly_reminders_task`)
- **Trigger:** Celery Beat schedule (1st day of every month at 00:05 UTC).
- **Functionality:** Identifies active recurring payments, calculates due dates taking month-end date variations into account, and issues reminder notifications.
- **Deduplication:** Verifies that no reminder notification has already been issued for the target recurring payment in the current billing cycle.

#### C. Asynchronous Excel Transaction Import (`process_excel_import_task`)
- **Trigger:** Enqueued via `POST /imports/async` or `POST /imports/excel/async`.
- **Workflow:**
  1. Uploaded file is staged into persistent volume (`IMPORT_STORAGE_PATH`).
  2. An `ImportJob` record is created in PostgreSQL with status `PENDING`.
  3. API immediately responds with HTTP 202 Accepted, returning `job_id` and `task_id`.
  4. Celery worker picks up task from `imports` queue, updates status to `PROCESSING`.
  5. Computes SHA-256 hash to verify staged file integrity.
  6. Parses workbook rows, executes validation checks, and calculates net financial impact.
  7. Inserts transactions atomically and commits to PostgreSQL.
  8. Invalidates affected user analytics cache in Redis.
  9. Updates `ImportJob` status to `COMPLETED` (or `FAILED` with sanitized error details).
  10. Automatically removes the staged Excel file from storage.

#### D. Notification Dispatch (`dispatch_notification_task`, `dispatch_bulk_notifications_task`)
- **Trigger:** System events, batch alerts, or scheduled summary completions.
- **Functionality:** Enqueues notification creation with optional deduplication keys to prevent spamming users upon duplicate events.

#### E. Analytics Cache Pre-warming (`warm_user_analytics_cache_task`)
- **Trigger:** Invoked post-batch import or following substantial data additions.
- **Functionality:** Precomputes daily and monthly analytics aggregations and populates Redis cache (DB 0) so user dashboard requests hit pre-warmed cache immediately.

### 4. Financial Integrity & Session Safety

Financial ledger accuracy is the core requirement of the Wallet Management API. Celery integration enforces strict financial invariants:

1. **Dedicated Database Sessions (`get_task_db`):**
   Tasks do not use the FastAPI `get_db` dependency. Instead, each task executes within the `get_task_db()` context manager:
   ```python
   with get_task_db() as db:
       # Fresh isolated session
       # Automatically rolls back on any exception
       # Guaranteed session closure in finally block
   ```
2. **Selective Transient Retries:**
   Tasks never retry permanent validation errors (e.g., invalid Excel format, insufficient wallet balance, duplicate constraints). Automatic retries (`autoretry_for=(OperationalError, DBAPIError)`) with exponential backoff (`countdown = 2 ** request.retries * 5`) only apply to transient connection dropouts.
3. **No Balance Mutation in Worker Retries:**
   Celery tasks never independently adjust wallet balances across retries. All balance recalculations are derived from atomic transaction inserts inside single database transactions.
4. **Late Acknowledgment & Worker Crash Recovery:**
   Configured with `task_acks_late = True` and `task_reject_on_worker_lost = True`. If a worker container crashes mid-task, unacknowledged tasks are re-queued rather than lost.
5. **Prefetch Control:**
   Configured with `worker_prefetch_multiplier = 1` to ensure heavy Excel import tasks are not monopolized by a single busy worker process.

### 5. Task Routing and Priority Queues

Tasks are dynamically routed to dedicated queues to prevent heavy bulk imports from starving high-frequency notifications or scheduled summaries:

| Queue | Tasks Routed | Concurrency Target |
|---|---|---|
| `imports` | `app.jobs.excel_import.process_excel_import_task` | Heavy CPU/IO workers |
| `scheduled` | `generate_daily_summaries_task`, `generate_monthly_reminders_task` | Periodic cron workers |
| `notifications` | `dispatch_notification_task`, `dispatch_bulk_notifications_task` | Fast I/O workers |
| `default` | General background tasks (`warm_user_analytics_cache_task`, etc.) | General pool |

### 6. Observability & Monitoring

1. **Structured Celery Signal Logging:**
   The application intercepts Celery signals (`task_prerun`, `task_postrun`, `task_failure`, `task_retry`) to emit structured JSON logs containing:
   - `task_id`, `task_name`
   - Execution duration (`runtime_seconds`)
   - Retry count and exception summary
   - User ID correlation
2. **Flower Web Dashboard:**
   A dedicated Flower dashboard is integrated into the Docker Compose stack at `http://127.0.0.1:5555/`:
   - Real-time worker health, concurrency, and queue depths
   - Task execution histories, latencies, and arguments
   - Basic HTTP authentication protection (`FLOWER_BASIC_AUTH=admin:walletadmin123`)

### 7. Troubleshooting & FAQ

- **Windows Worker Setup (`ValueError: not enough values to unpack`):**
  On Windows, Celery's default prefork pool encounters subprocess restrictions. Always start local workers on Windows with `--pool=solo`:
  ```powershell
  celery -A app.celery_app.celery_app worker --pool=solo --loglevel=INFO -Q imports,scheduled,notifications,default
  ```
- **Redis Connection Errors During Task Status Polling:**
  The `GET /tasks/{task_id}` and `GET /imports/{import_id}/status` endpoints include resilient fallback to the PostgreSQL `ImportJob` ledger if the Celery result backend is temporarily unreachable.
- **Docker Shared Volume Permissions:**
  The `shared_data` volume is mounted at `/app/data` across both `api` and `celery_worker` containers, ensuring files uploaded via the API container are immediately readable by background worker containers.

## Test Suite

Run the complete test suite:

```powershell
python -m pytest
```

The test suite covers comprehensive test modules across all layers (68 automated tests, 100% passing):
- `tests/test_celery_config.py`: 6 tests verifying Celery initialization, Redis DB isolation (DB 1 broker, DB 2 backend), serializer security (JSON only), late acknowledgements, worker crash recovery, queue routing, and Beat cron registrations.
- `tests/test_celery_tasks.py`: 7 tests covering end-to-end task execution: daily financial summary calculation, single-user summary, monthly recurring reminders with deduplication, asynchronous Excel import success and transaction creation, Excel validation failure handling, async notification dispatch, and analytics cache warming.
- `tests/test_celery_db.py`: 3 tests validating database session management: independent session creation, reliable session closure, automatic rollback on task exception, and connection pool leak prevention under repeated failures.
- `tests/test_celery_api.py`: 4 tests validating REST API endpoints: `POST /imports/async` (HTTP 202 Accepted), `GET /imports/{id}/status` progress polling, `GET /tasks/{id}` status querying, cross-user authorization enforcement (HTTP 403 Forbidden), unknown ID handling (HTTP 404 Not Found), and unauthenticated request protection (HTTP 401 Unauthorized).
- `tests/test_redis_caching_and_ratelimit.py`: 20 dedicated test cases for Redis client lifecycle, cache miss/hit, TTL recomputation, user cache isolation, PostgreSQL fallback, serialization error recovery, transaction creation/update/deletion invalidation, Excel import invalidation, atomic Lua sliding-window rate limiting, HTTP 429 + `Retry-After`, login IP resolution, trusted proxy handling, fail-open vs fail-closed policy, and separate Redis/PostgreSQL health status reporting.
- `tests/test_mode_of_payment_refactor.py`: 14 dedicated test cases for automatic mini-wallet resolution, normalization, uniqueness constraints, concurrent requests, cross-user isolation, Excel row-level resolution and atomic rollback, financial integrity, and migration compatibility.
- `tests/test_phase1_auth.py`: Authentication, JWT tokens, user profiles, wallet hierarchy isolation.
- `tests/test_phase2_transactions.py`: Financial engine, income/expense calculations, transaction update/delete.
- `tests/test_phase3_analytics.py`: Daily/monthly/yearly aggregations, chart data formats, budget targets.
- `tests/test_phase4_features.py`: Excel imports, savings goals, debt tracking, recurring reminders, proof uploads.
- `tests/test_financial_integrity.py`: Atomic balance mutations, reversal logic, insufficient balance constraints, withdrawal/repayment invariants.
- `tests/test_phase5_hardening.py`: Health checks, observability headers (`X-Request-ID`), security headers, cross-user isolation, pagination limits, input validation edge cases.
