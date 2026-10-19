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
- Daily, monthly, and yearly analytics, category breakdowns, and chart data
- Daily and monthly budgets with status checks
- Excel transaction preview, per-row mini-wallet resolution, validation, and atomic import
- Savings goals, contributions, withdrawals, and progress
- Separate investment records
- Lent/borrowed debt tracking and repayment history
- Monthly recurring payments
- Scheduled daily summaries and monthly reminder notifications

## Technology

- Python 3.10+
- FastAPI, Pydantic, SQLAlchemy
- PostgreSQL (via psycopg)
- APScheduler for in-process scheduled jobs
- openpyxl for `.xlsx` imports

## Project structure

```text
app/
├── core/          # Authentication and request dependencies
├── jobs/          # Daily summary and monthly reminder jobs
├── routers/       # HTTP endpoints
├── schema/        # Pydantic request/response models
├── services/      # Business logic
├── database.py    # SQLAlchemy engine, sessions, and table initialization
├── main.py        # FastAPI application and router/scheduler setup
└── models.py      # SQLAlchemy models
tests/             # API tests for Phases 1–4
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

# Background Job Scheduler (true/false)
SCHEDULER_ENABLED=true

# Logging Level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Proof File Storage Directory
FILE_STORAGE_PATH=app/data
```

`DATABASE_URL` is required. `SECRET_KEY` should be set to a private random value in every non-test environment. Set `SCHEDULER_ENABLED=false` when running multiple worker processes or replica containers so that only the primary node runs scheduled jobs.

### Proof image storage

Transaction proof images are stored locally under `FILE_STORAGE_PATH` (defaults to `app/data/proofs`). Uploads are verified via MIME-type and magic-byte signatures (JPEG, PNG, GIF, WebP) with a 5 MB maximum size limit.

## Run Locally

From the repository root with virtual environment activated:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The API is available at:

- API root: <http://127.0.0.1:8000/>
- Health check (includes database status): <http://127.0.0.1:8000/health>
- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>

## Run with Docker Compose

To run the complete production-ready stack (PostgreSQL + FastAPI service with health checks):

```powershell
docker compose up --build -d
```

View application logs:

```powershell
docker compose logs -f api
```

Stop the containers:

```powershell
docker compose down
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
| `POST` | `/imports/excel` | Validate and import workbook in one atomic batch |

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

## Test Suite

Run the complete test suite:

```powershell
pytest
```

The test suite covers comprehensive test modules across all layers:
- `tests/test_mode_of_payment_refactor.py`: 14 dedicated test cases for automatic mini-wallet resolution, normalization, uniqueness constraints, concurrent requests, cross-user isolation, Excel row-level resolution and atomic rollback, financial integrity, and migration compatibility.
- `tests/test_phase1_auth.py`: Authentication, JWT tokens, user profiles, wallet hierarchy isolation.
- `tests/test_phase2_transactions.py`: Financial engine, income/expense calculations, transaction update/delete.
- `tests/test_phase3_analytics.py`: Daily/monthly/yearly aggregations, chart data formats, budget targets.
- `tests/test_phase4_features.py`: Excel imports, savings goals, debt tracking, recurring reminders, proof uploads.
- `tests/test_financial_integrity.py`: Atomic balance mutations, reversal logic, insufficient balance constraints, withdrawal/repayment invariants.
- `tests/test_phase5_hardening.py`: Health checks, observability headers (`X-Request-ID`), security headers, cross-user isolation, pagination limits, input validation edge cases.

## Explicitly Deferred Items

1. **Distributed Task Queue / Broker (e.g., Celery / Redis):** Multi-node distributed queue deferred; using robust in-process APScheduler with concurrency locks and database deduplication keys.
2. **Live External Email/SMS Delivery Providers:** Third-party gateway credentials deferred; in-app notifications generated, deduplicated, and retrievable via `/notifications`.
3. **External S3 Cloud Object Storage:** Cloud S3 credentials deferred; secure local filesystem proof storage at `FILE_STORAGE_PATH` with validation and size limits.
4. **Persisted Pre-Aggregated Balance Caching & Cursor Pagination:** Persisted caching deferred to guarantee transactions as the single source of financial truth; query performance maintained via indexes and bounded limit/offset pagination.
