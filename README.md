# Wallet Management API

A FastAPI backend for managing user wallets, income and expense transactions, budgets, financial goals, and recurring-payment reminders. It uses SQLAlchemy for persistence and PostgreSQL in production.

## Features

- JWT bearer authentication and user-scoped API access
- One super wallet per user, with multiple mini wallets
- Income and expense transactions with balances derived from transaction history
- Transaction filtering, pagination, and text/image proof references
- Daily, monthly, and yearly analytics, category breakdowns, and chart data
- Daily and monthly budgets with status checks
- Excel transaction preview, validation, and import
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

### 3. Configure PostgreSQL

Create a PostgreSQL database and a user with permission to connect and create tables. Set the following environment variables in a root `.env` file:

```dotenv
DATABASE_URL=postgresql+psycopg://wallet_user:your-password@localhost:5432/wallet_management
SECRET_KEY=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30
```

`DATABASE_URL` is required. The application reads `.env` using `python-dotenv`. `SECRET_KEY` should be set to a private random value in every non-test environment; the development default in the code is not suitable for production. `JWT_ALGORITHM` and `JWT_EXPIRE_MINUTES` are optional and default to `HS256` and `30`.

The application calls SQLAlchemy `create_all()` at startup to create missing tables. This does not alter existing tables or replace a database migration process when schemas change.

### Optional: proof image storage

Transaction proof images are stored locally. By default, files are written to `app/data/proofs`. Set `FILE_STORAGE_PATH` to choose a different base directory; images are then written to its `proofs` subdirectory. The configured storage must be durable and backed up if proof files need to survive deployments.

## Run

From the repository root:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The API is available at:

- API root: <http://127.0.0.1:8000/>
- Health check: <http://127.0.0.1:8000/health>
- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>

## Authentication

Register and log in using JSON:

```http
POST /auth/register
Content-Type: application/json

{
  "name": "Avery",
  "phone": "5551234567",
  "email": "avery@example.com",
  "currency": "USD",
  "password": "choose-a-strong-password"
}
```

```http
POST /auth/login
Content-Type: application/json

{
  "email": "avery@example.com",
  "password": "choose-a-strong-password"
}
```

Use the returned `access_token` on protected endpoints:

```http
Authorization: Bearer <access_token>
```

## API endpoints

All endpoints require bearer authentication except registration, login, the root endpoint, and the health check. Wallet, transaction, savings, investment, debt, recurring-payment, and notification operations are restricted to the authenticated user's records.

### Users and wallets

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a user |
| `POST` | `/auth/login` | Get an access token |
| `GET` | `/users/me` | Get the current user |
| `PUT` | `/users/me` | Update the current user |
| `POST` | `/super-wallet` | Create the user's super wallet |
| `GET` | `/super-wallet` | Get the user's super wallet |
| `PUT` | `/super-wallet` | Update the user's super wallet |
| `POST` | `/super-wallet/mini-wallets` | Create a mini wallet |
| `GET` | `/super-wallet/mini-wallets` | List mini wallets |
| `GET` | `/mini-wallets/{mini_wallet_id}` | Get a mini wallet |
| `PUT` | `/mini-wallets/{mini_wallet_id}` | Update a mini wallet |
| `DELETE` | `/mini-wallets/{mini_wallet_id}` | Delete a mini wallet |
| `GET` | `/mini-wallets/{mini_wallet_id}/balance` | Get a mini-wallet balance |
| `GET` | `/super-wallet/balance` | Get the super-wallet balance |

The app also exposes wallet-compatible routes under `/wallets` for clients using the older wallet API:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/wallets` | Create a wallet |
| `GET` | `/wallets` | List the current user's wallets |
| `GET` | `/wallets/{wallet_id}` | Get a wallet |
| `PUT` | `/wallets/{wallet_id}` | Update a wallet |
| `DELETE` | `/wallets/{wallet_id}` | Delete a wallet |

### Transactions

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/mini-wallets/{mini_wallet_id}/transactions` | Create an income or expense |
| `GET` | `/mini-wallets/{mini_wallet_id}/transactions` | List a mini wallet's transactions |
| `GET` | `/super-wallet/transactions` | List transactions across the super wallet |
| `GET` | `/transactions/{transaction_id}` | Get a transaction |
| `PUT` | `/transactions/{transaction_id}` | Update a transaction |
| `DELETE` | `/transactions/{transaction_id}` | Delete a transaction |
| `POST` | `/transactions/{transaction_id}/proof` | Attach text or image proof |
| `GET` | `/transactions/{transaction_id}/proof` | Retrieve the transaction proof |

Transaction list endpoints accept `date_from`, `date_to`, `type`, `category`, `modeofpayment`, `limit`, and `offset`. The super-wallet list also accepts `mini_wallet_id`. The default limit is 50.

Balances are calculated from transactions; they are not maintained as independently editable balance fields. Transaction amounts must be positive, types are `income` or `expense`, and an expense cannot exceed the mini-wallet's available balance.

### Analytics and budgets

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/analytics/daily?date=YYYY-MM-DD` | Daily income, expense, net, category and mini-wallet totals |
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

### Imports and proof

Excel endpoints use `multipart/form-data`. Include `mini_wallet_id` and a file field named `file`. Workbooks must be `.xlsx` and no larger than 10 MB. Required columns are `amount`, `type`, `category`, `date_created`, `modeofpayment`, and `description`; `proof` is optional. Dates must be Excel dates or ISO-formatted date/datetime values.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/imports/excel/preview` | Validate and preview rows without inserting transactions |
| `POST` | `/imports/excel/confirm` | Confirm the same workbook using `preview_sha256` from the preview response |
| `POST` | `/imports/excel` | Validate and import a workbook in one operation |

The preview response provides `file_sha256`, which must be sent as the `preview_sha256` form field to confirm. The confirmation endpoint requires the same file bytes and revalidates the workbook and wallet balance before inserting. Duplicate rows are allowed and inserted separately; no automatic deduplication is performed. A failed import is rolled back as a batch.

Proof can be supplied as text or as a JPEG, PNG, GIF, or WebP image up to 5 MB. Image filenames are generated by the application; only a storage reference is saved in the transaction.

### Savings, investments, debt, and recurring payments

| Method | Endpoint | Description |
|---|---|---|
| `POST` / `GET` | `/savings` | Create and list savings goals |
| `PUT` / `DELETE` | `/savings/{goal_id}` | Update or delete a savings goal |
| `POST` | `/savings/{goal_id}/contributions` | Add or withdraw savings (`action`: `add` or `withdraw`) |
| `POST` / `GET` | `/investments` | Create and list investment records |
| `GET` / `PUT` / `DELETE` | `/investments/{investment_id}` | Get, update, or delete an investment |
| `POST` / `GET` | `/debts` | Create and list lent or borrowed records |
| `PUT` / `DELETE` | `/debts/{debt_id}` | Update or delete a debt |
| `POST` | `/debts/{debt_id}/repayments` | Record a repayment |
| `POST` / `GET` | `/recurring-payments` | Create and list recurring payments |
| `PUT` / `DELETE` | `/recurring-payments/{payment_id}` | Update or delete a recurring payment |

Recurring payments currently support monthly frequency only. Debt directions are `lent` and `borrowed`; status is derived from the remaining amount and is `pending`, `partially_paid`, or `settled`.

### Notifications and scheduled jobs

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/notifications` | List notifications; supports `unread_only`, `limit`, and `offset` |
| `POST` | `/notifications/{notification_id}/read` | Mark a notification as read |

On application startup, an in-process APScheduler runs the daily summary at 23:59 UTC and generates recurring-payment reminders at 00:05 UTC on the first day of each month. Generated notifications are stored for retrieval through `/notifications`; email and SMS delivery are not configured. Use a single scheduler instance or a durable external scheduler/queue when deploying multiple API instances.

## Test

With dependencies installed, run the complete suite from the repository root:

```powershell
python -m pytest -q
```

The tests use SQLite databases and cover authentication, transactions, analytics, and Phase 4 workflows.
