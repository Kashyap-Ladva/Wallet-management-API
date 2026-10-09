# Wallet Management API

A beginner-friendly wallet management REST API built with FastAPI. The project uses PostgreSQL with SQLAlchemy ORM for persistence and demonstrates API routing, Pydantic validation, CRUD operations, business logic, and error handling.

## Features

- Create, list, retrieve, update, and delete wallets
- Record income and expense transactions
- Automatically update wallet balances
- Prevent expenses greater than the available balance
- Retrieve transaction history
- Update and delete transactions while correcting the wallet balance
- View wallet balance and spending summaries
- Group expenses by category
- Interactive Swagger documentation

## Technology

- Python
- FastAPI
- Uvicorn
- Pydantic
- PostgreSQL
- SQLAlchemy ORM

## Project Structure

```text
app/
├── main.py
├── database.py
├── models.py
├── routers/
│   ├── wallets.py
│   └── transactions.py
├── schema/
│   ├── wallet.py
│   └── transaction.py
└── services/
    ├── wallet_service.py
    └── transaction_service.py
```

## Setup

Create and activate a virtual environment on Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a PostgreSQL database and application user (run in `psql` as a PostgreSQL administrator):

```sql
CREATE USER wallet_user WITH PASSWORD 'choose_a_password';
CREATE DATABASE wallet_management OWNER wallet_user;
```

Copy `.env.example` to `.env` and set `DATABASE_URL` to your PostgreSQL connection URL. For a local server, use:

```text
DATABASE_URL=postgresql+psycopg://wallet_user:choose_a_password@localhost:5432/wallet_management
```

Keep `.env` private; it is excluded from version control. On startup, SQLAlchemy creates any missing tables defined by the application models. `create_all` does not migrate existing tables; use a database migration when changing an existing schema.

## Run the API

From the project root:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The API is available at:

- http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## API Endpoints

### Application

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API welcome message |
| `GET` | `/health` | Health check |

### Wallets

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/wallets` | Create a wallet |
| `GET` | `/wallets` | List all wallets |
| `GET` | `/wallets/{wallet_id}` | Get one wallet |
| `PUT` | `/wallets/{wallet_id}` | Update wallet name or currency |
| `DELETE` | `/wallets/{wallet_id}` | Delete a wallet |

Create-wallet example:

```json
{
  "name": "My Wallet",
  "currency": "INR"
}
```

Example response:

```json
{
  "id": 1,
  "name": "My Wallet",
  "currency": "INR",
  "balance": 0
}
```

### Transactions

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/wallets/{wallet_id}/transactions` | Add income or expense |
| `GET` | `/wallets/{wallet_id}/transactions` | List wallet transactions |
| `GET` | `/transactions/{transaction_id}` | Get one transaction |
| `PUT` | `/transactions/{transaction_id}` | Update a transaction |
| `DELETE` | `/transactions/{transaction_id}` | Delete a transaction |

Create-transaction example:

```json
{
  "amount": 5000,
  "type": "income",
  "category": "salary",
  "description": "Monthly salary"
}
```

Supported transaction types are `income` and `expense`. Amounts must be greater than zero.

### Reports

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/wallets/{wallet_id}/balance` | Get current balance |
| `GET` | `/wallets/{wallet_id}/summary` | Get income, expense, and balance totals |
| `GET` | `/wallets/{wallet_id}/expenses/category` | Get expense totals grouped by category |

### Phase 4 — Imports and financial records

All endpoints below require a bearer access token. Excel imports accept `.xlsx` files up to 10 MB and require `amount`, `type`, `category`, `date_created`, `modeofpayment`, and `description` columns. A `proof` column is optional and stores the existing transaction proof reference.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/imports/excel/preview` | Validate an uploaded workbook for the selected owned `mini_wallet_id`; returns a SHA-256 preview token and row errors |
| `POST` | `/imports/excel/confirm` | Re-upload the same workbook with `mini_wallet_id` and `preview_sha256` to atomically import it |
| `POST` | `/imports/excel` | Validate the complete workbook and import it atomically without a separate preview |
| `POST` / `GET` | `/transactions/{transaction_id}/proof` | Add or retrieve an owned transaction's text or image proof |
| `POST` / `GET` | `/savings` | Create and list savings goals |
| `PUT` / `DELETE` | `/savings/{goal_id}` | Update or delete an owned savings goal |
| `POST` | `/savings/{goal_id}/contributions` | Add to or withdraw from a goal |
| `POST` / `GET` | `/investments` | Create and list investment records |
| `GET` / `PUT` / `DELETE` | `/investments/{investment_id}` | Retrieve, update, or delete an owned investment |
| `POST` / `GET` | `/debts` | Create and list lent or borrowed records |
| `PUT` / `DELETE` | `/debts/{debt_id}` | Update or delete an owned debt record |
| `POST` | `/debts/{debt_id}/repayments` | Record a repayment and update remaining amount/status |
| `POST` / `GET` | `/recurring-payments` | Create and list monthly recurring payments |
| `PUT` / `DELETE` | `/recurring-payments/{payment_id}` | Update or delete an owned recurring payment |
| `GET` | `/notifications` | List stored daily summaries and recurring-payment reminders |
| `POST` | `/notifications/{notification_id}/read` | Mark an owned notification as read |

Duplicate import rows are intentionally allowed and inserted as separate transactions; the importer does not attempt to infer whether identical rows are accidental duplicates. The daily summary runs at 23:59 UTC, and monthly reminders run at 00:05 UTC on the first day of each month. Jobs store notifications for retrieval through `/notifications`; no email or SMS delivery provider is configured. The in-process scheduler is intended for a single application instance; use a durable scheduler/queue or a single designated scheduler process when deploying multiple API instances.

Proof text is stored in the transaction's `proof` field. Images must be JPEG, PNG, GIF, or WebP and are limited to 5 MB; they are stored under `app/data/proofs` by default, or under `<FILE_STORAGE_PATH>/proofs` when `FILE_STORAGE_PATH` is configured. Only a generated storage key is stored in the transaction.

## Error Handling

The API returns meaningful HTTP errors, including:

- `404` when a wallet or transaction does not exist
- `400` when an expense exceeds the available balance
- `422` when request validation fails

## Data Storage

Data is stored in the PostgreSQL database specified by `DATABASE_URL`.

If the `wallets` table does not exist, the existing JSON files are imported once:

```text
app/data/wallets.json
app/data/transactions.json
```

After initialization, the JSON files are not used for reads or writes.
