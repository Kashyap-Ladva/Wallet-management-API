# Wallet Management API

A beginner-friendly wallet management REST API built with FastAPI. The project uses SQLite with SQLAlchemy ORM for persistence and demonstrates API routing, Pydantic validation, CRUD operations, business logic, and error handling.

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
- SQLite
- SQLAlchemy ORM

## Project Structure

```text
app/
├── main.py
├── data/
│   ├── wallets.json
│   └── transactions.json
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

## Error Handling

The API returns meaningful HTTP errors, including:

- `404` when a wallet or transaction does not exist
- `400` when an expense exceeds the available balance
- `422` when request validation fails

## Data Storage

Data is stored locally in `wallets.db`, which is created automatically on first startup.

If `wallets.db` does not exist, the existing JSON files are imported once:

```text
app/data/wallets.json
app/data/transactions.json
```

After initialization, the JSON files are not used for reads or writes.
