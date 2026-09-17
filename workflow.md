# Wallet Management API — Simple Workflow

## Basic Flow

```text
User
  ↓
FastAPI Router
  ↓
Pydantic Schema
  ↓
Service
      ↓
SQLAlchemy ORM
      ↓
SQLite Database
  ↓
Response
```

## Wallet Flow

```text
Create / View / Update / Delete Wallet
              ↓
        Wallet Router
              ↓
        Wallet Service
              ↓
                        SQLAlchemy ORM
                                          ↓
                              SQLite
```

## Transaction Flow

```text
Add Transaction
      ↓
Transaction Router
      ↓
Transaction Service
      ↓
Check Wallet
      ↓
Income / Expense
      ↓
Update Balance
      ↓
SQLAlchemy ORM
      ↓
SQLite Database
```

## Overall Project

```text
                Wallet Management API
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
           Wallets             Transactions
              ↓                     ↓
         CRUD Operations       Add / View / Update
              ↓                     ↓
              └──────────┬──────────┘
                         ↓
                SQLAlchemy ORM
                         ↓
                   SQLite Database
```

## Main Components

- **Router** → Handles API requests.
- **Schema** → Validates input data.
- **Service** → Contains the main logic.
- **SQLAlchemy ORM** → Maps wallets and transactions to database tables.
- **SQLite Database** → Stores wallet and transaction data in `wallets.db`.

## Final Goal

Build a simple Wallet Management API that:

1. Manages wallets.
2. Handles income and expenses.
3. Updates wallet balance.
4. Stores data in SQLite through SQLAlchemy ORM.
5. Provides useful transaction information.
