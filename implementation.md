# Wallet Management API — Implementation Guide

This document explains **how we will actually build the project** described in `plan.md`.

The project is intentionally implemented step-by-step so that every part teaches a FastAPI concept.

> **Learning rule:** Do not build the entire project in one shot. Complete a phase, run it, test it, understand it, then move forward.

---

# 1. Project Setup

## 1.1 Create the project

Create a folder:

```text
wallet-management
```

Open the folder in VS Code.

## 1.2 Create a virtual environment

Windows:

```bash
python -m venv venv
```

Activate it:

```bash
venv\Scripts\activate
```

## 1.3 Install initial dependencies

Start with only what we need:

```bash
pip install fastapi uvicorn
```

Later we will install:

```bash
pip install scikit-learn joblib pytest httpx
```

Do not install everything at the beginning.

## 1.4 Save dependencies

```bash
pip freeze > requirements.txt
```

---

# 2. Phase 1 — Create the FastAPI Application

## Files

Initially create only:

```text
wallet-management/
│
├── app/
│   └── main.py
│
└── requirements.txt
```

## `main.py`

The first version should be very small:

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Wallet Management API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
```

## Run

From the project root:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## What to understand

Understand:

```python
app = FastAPI()
```

```python
@app.get("/")
```

```python
def home():
```

and why:

```text
app.main:app
```

is used by Uvicorn.

Do not move ahead until these are clear.

---

# 3. Phase 2 — Understand HTTP Methods

Before implementing CRUD, create simple examples for:

```text
GET
POST
PUT
DELETE
```

Conceptually:

```text
GET     → retrieve data
POST    → create data
PUT     → update data
DELETE  → remove data
```

Example:

```python
@app.post("/test")
def create_test():
    return {"message": "created"}
```

The goal is to understand how FastAPI maps HTTP methods to Python functions.

---

# 4. Phase 3 — Pydantic Request Models

Now introduce Pydantic.

Create:

```text
app/
├── main.py
└── schemas/
    └── wallet.py
```

## `wallet.py`

Start with:

```python
from pydantic import BaseModel


class WalletCreate(BaseModel):
    name: str
    currency: str
```

Then use it in an endpoint:

```python
from fastapi import FastAPI
from app.schemas.wallet import WalletCreate

app = FastAPI()


@app.post("/wallets")
def create_wallet(wallet: WalletCreate):
    return wallet
```

Test through Swagger.

Send:

```json
{
    "name": "My Wallet",
    "currency": "INR"
}
```

## What to understand

The important flow is:

```text
JSON request
     ↓
Pydantic model
     ↓
Validation
     ↓
Python object
     ↓
FastAPI endpoint
```

Try invalid input yourself.

For example:

```json
{
    "name": 123
}
```

Observe what FastAPI/Pydantic does.

---

# 5. Phase 4 — File Storage

Now introduce file operations.

Create:

```text
app/
├── main.py
├── schemas/
│   └── wallet.py
└── data/
    └── wallets.json
```

Initial file:

```json
[]
```

Keep the storage format simple.

## Create file helper functions

Create:

```text
app/
└── services/
    └── wallet_service.py
```

Initially:

```python
import json

FILE_PATH = "app/data/wallets.json"


def read_wallets():
    with open(FILE_PATH, "r") as file:
        return json.load(file)


def save_wallets(wallets):
    with open(FILE_PATH, "w") as file:
        json.dump(wallets, file, indent=4)
```

## What to understand

Learn:

```python
open()
```

```python
json.load()
```

```python
json.dump()
```

and:

```text
read file
    ↓
convert JSON → Python
    ↓
modify Python data
    ↓
convert Python → JSON
    ↓
write file
```

Do not add databases yet.

---

# 6. Phase 5 — Wallet CRUD

Now implement the actual wallet CRUD.

## Wallet data

A wallet can initially look like:

```json
{
    "id": 1,
    "name": "My Wallet",
    "currency": "INR",
    "balance": 0
}
```

## Endpoints

### Create

```text
POST /wallets
```

Flow:

```text
Request
  ↓
Validate with Pydantic
  ↓
Read wallets.json
  ↓
Generate ID
  ↓
Add wallet
  ↓
Save wallets.json
  ↓
Return wallet
```

### Get all

```text
GET /wallets
```

Flow:

```text
Request
  ↓
Read JSON
  ↓
Return wallets
```

### Get one

```text
GET /wallets/{wallet_id}
```

Flow:

```text
wallet_id
    ↓
Read JSON
    ↓
Search wallet
    ↓
Found → return
Not found → HTTPException 404
```

### Update

```text
PUT /wallets/{wallet_id}
```

Flow:

```text
Find wallet
    ↓
Update fields
    ↓
Save file
    ↓
Return updated wallet
```

### Delete

```text
DELETE /wallets/{wallet_id}
```

Flow:

```text
Find wallet
    ↓
Remove wallet
    ↓
Save file
    ↓
Return confirmation
```

---

# 7. Phase 6 — Improve Schemas

Separate input and output models.

For example:

```python
class WalletCreate(BaseModel):
    name: str
    currency: str


class WalletUpdate(BaseModel):
    name: str | None = None
    currency: str | None = None


class WalletResponse(BaseModel):
    id: int
    name: str
    currency: str
    balance: float
```

This teaches an important API concept:

```text
What the client sends
        ≠
What the API returns
```

---

# 8. Phase 7 — Transaction Model

Create:

```text
app/
└── schemas/
    └── transaction.py
```

Initial model:

```python
from pydantic import BaseModel


class TransactionCreate(BaseModel):
    amount: float
    type: str
    category: str
    description: str | None = None
```

A transaction:

```json
{
    "amount": 5000,
    "type": "income",
    "category": "salary",
    "description": "Monthly salary"
}
```

Initially support:

```text
income
expense
```

Later, validation can be improved with an enum or stricter validation.

---

# 9. Phase 8 — Transaction File

Create:

```text
app/data/transactions.json
```

Initial contents:

```json
[]
```

Transaction example:

```json
{
    "id": 1,
    "wallet_id": 1,
    "amount": 5000,
    "type": "income",
    "category": "salary",
    "description": "Monthly salary"
}
```

Notice that each transaction has:

```text
wallet_id
```

This connects a transaction to a wallet.

---

# 10. Phase 9 — Add Transaction API

Create:

```text
POST /wallets/{wallet_id}/transactions
```

Implementation logic:

```text
Receive wallet_id
       ↓
Check wallet exists
       ↓
Validate transaction
       ↓
Generate transaction ID
       ↓
Save transaction
       ↓
Update wallet balance
       ↓
Save wallet
       ↓
Return transaction
```

## Income

```text
balance = balance + amount
```

## Expense

```text
balance = balance - amount
```

For an expense, check:

```text
amount <= current balance
```

If not:

```text
HTTP 400
Insufficient balance
```

---

# 11. Phase 10 — Transaction CRUD

Implement:

```text
POST   /wallets/{wallet_id}/transactions
GET    /wallets/{wallet_id}/transactions

GET    /transactions/{transaction_id}
PUT    /transactions/{transaction_id}
DELETE /transactions/{transaction_id}
```

## Important learning point

Updating/deleting a transaction can affect the wallet balance.

Example:

Original:

```text
Income ₹10,000
Expense ₹2,000

Balance = ₹8,000
```

If the ₹2,000 expense is deleted:

```text
Balance = ₹10,000
```

Therefore transaction operations require careful business logic.

---

# 12. Phase 11 — Wallet Summary

Add:

```text
GET /wallets/{wallet_id}/balance
```

Response:

```json
{
    "wallet_id": 1,
    "balance": 25000
}
```

Add:

```text
GET /wallets/{wallet_id}/summary
```

Response:

```json
{
    "wallet_id": 1,
    "balance": 25000,
    "total_income": 40000,
    "total_expense": 15000
}
```

The API calculates these values from transactions.

---

# 13. Phase 12 — Category-wise Expenses

Add:

```text
GET /wallets/{wallet_id}/expenses/category
```

Example:

```json
{
    "food": 3000,
    "travel": 2000,
    "shopping": 5000
}
```

Implementation concept:

```text
Get transactions
       ↓
Filter expenses
       ↓
Group by category
       ↓
Add amounts
       ↓
Return dictionary
```

This is useful Python practice as well as FastAPI practice.

---

# 14. Phase 13 — Error Handling

Use:

```python
from fastapi import HTTPException
```

Examples:

## Wallet doesn't exist

```python
raise HTTPException(
    status_code=404,
    detail="Wallet not found"
)
```

## Transaction doesn't exist

```text
404
```

## Invalid amount

```text
400
```

## Insufficient balance

```text
400
```

## Invalid transaction type

```text
400
```

The goal is to understand why different HTTP status codes exist.

---

# 15. Phase 14 — Separate Router Files

Once the basic application becomes large, split routes.

Structure:

```text
app/
├── main.py
│
├── routers/
│   ├── wallets.py
│   └── transactions.py
│
├── schemas/
│   ├── wallet.py
│   └── transaction.py
│
├── services/
│   ├── wallet_service.py
│   └── transaction_service.py
│
└── data/
    ├── wallets.json
    └── transactions.json
```

`main.py` should become the application entry point.

Conceptually:

```text
main.py
   │
   ├── wallet router
   │
   └── transaction router
```

This introduces FastAPI's `APIRouter`.

Do this only after understanding the simpler version.

---

# 16. Phase 15 — Machine Learning

Only after the wallet API is working.

Create:

```text
ml/
├── train_model.py
└── model.pkl
```

## Dataset

Use monthly expense history.

Example:

```text
Month    Expense
1        12000
2        14000
3        13500
4        15000
5        16000
```

Feature:

```text
month
```

Target:

```text
expense
```

## Model

Start with:

```text
LinearRegression
```

Training flow:

```text
Historical data
       ↓
Prepare X and y
       ↓
Train/test split
       ↓
Train Linear Regression
       ↓
Evaluate
       ↓
Save model
```

Save with `joblib`.

---

# 17. Phase 16 — Connect ML to FastAPI

Create:

```text
app/services/prediction_service.py
```

The service loads the trained model and performs prediction.

Endpoint:

```text
POST /wallets/{wallet_id}/predict-expense
```

Flow:

```text
API request
     ↓
Get wallet transactions
     ↓
Extract historical expenses
     ↓
Prepare ML input
     ↓
Load model
     ↓
Predict
     ↓
Return prediction
```

Example:

```json
{
    "wallet_id": 1,
    "predicted_expense": 16800
}
```

---

# 18. Phase 17 — Testing

Create:

```text
tests/
├── test_wallets.py
└── test_transactions.py
```

Test important behavior.

## Wallet tests

```text
Create wallet
Get wallets
Get wallet by ID
Update wallet
Delete wallet
Wallet not found
```

## Transaction tests

```text
Add income
Add expense
Check balance
Get transactions
Update transaction
Delete transaction
Insufficient balance
Invalid transaction
```

The goal is not to write hundreds of tests.

The goal is to learn how API testing works.

---

# 19. Phase 18 — Final Testing Flow

Perform a complete manual flow through Swagger:

```text
1. Create wallet
       ↓
2. Get wallet
       ↓
3. Add ₹30,000 income
       ↓
4. Check balance
       ↓
5. Add ₹2,000 food expense
       ↓
6. Add ₹1,500 travel expense
       ↓
7. Check balance
       ↓
8. View transactions
       ↓
9. View summary
       ↓
10. View category expenses
       ↓
11. Predict next month's expense
       ↓
12. Update a transaction
       ↓
13. Delete a transaction
       ↓
14. Delete wallet
```

---

# 20. Final Project Structure

After implementation:

```text
wallet-management/
│
├── app/
│   ├── main.py
│   │
│   ├── routers/
│   │   ├── wallets.py
│   │   └── transactions.py
│   │
│   ├── schemas/
│   │   ├── wallet.py
│   │   └── transaction.py
│   │
│   ├── services/
│   │   ├── wallet_service.py
│   │   ├── transaction_service.py
│   │   └── prediction_service.py
│   │
│   └── data/
│       ├── wallets.json
│       └── transactions.json
│
├── ml/
│   ├── train_model.py
│   └── model.pkl
│
├── tests/
│   ├── test_wallets.py
│   └── test_transactions.py
│
├── requirements.txt
├── README.md
├── plan.md
└── implementation.md
```

---

# 21. Implementation Order

Follow this exact order:

```text
[1] Project setup
        ↓
[2] FastAPI app
        ↓
[3] GET/POST/PUT/DELETE basics
        ↓
[4] Pydantic
        ↓
[5] JSON file operations
        ↓
[6] Wallet CRUD
        ↓
[7] Transaction model
        ↓
[8] Transaction CRUD
        ↓
[9] Balance logic
        ↓
[10] Summary APIs
        ↓
[11] Error handling
        ↓
[12] Router structure
        ↓
[13] ML model
        ↓
[14] ML + FastAPI
        ↓
[15] Testing
        ↓
[16] README/documentation
```

---

# 22. Rules While Building

## Rule 1 — No SQLAlchemy initially

The project should first work with JSON files.

## Rule 2 — No unnecessary architecture

If a simple function solves the problem, use the simple function.

## Rule 3 — Understand before moving on

For every new FastAPI feature, understand:

```text
What is it?
Why are we using it?
What problem does it solve?
How does it work?
```

## Rule 4 — Test every phase

Never write 10 files and then discover everything is broken.

Run and test after every meaningful change.

## Rule 5 — ML comes last

Do not let the ML component distract from learning FastAPI.

---

# 23. What You Should Be Able to Explain to Your TL

At the end of the project, you should be able to explain:

### FastAPI

- What FastAPI is
- How an endpoint works
- What `FastAPI()` does
- What `APIRouter` does
- GET vs POST vs PUT vs DELETE
- Path parameters
- Query parameters
- Request bodies
- Response models
- HTTP status codes
- `HTTPException`
- Swagger/OpenAPI

### Pydantic

- What `BaseModel` does
- Request validation
- Response validation
- Required vs optional fields

### File operations

- Reading JSON
- Writing JSON
- Converting JSON to Python objects
- Converting Python objects to JSON

### Application design

```text
Router
  ↓
Schema
  ↓
Service/business logic
  ↓
File storage
```

### ML

- What the model predicts
- What features are used
- What the target is
- How the model is trained
- How the model is saved
- How FastAPI calls the model

---

# 24. First Milestone

The first milestone is intentionally tiny.

You should reach:

```text
wallet-management/
│
├── app/
│   └── main.py
│
└── requirements.txt
```

and successfully run:

```bash
uvicorn app.main:app --reload
```

Then verify:

```text
GET /
GET /health
/docs
```

Once this works, stop.

**Do not create the wallet CRUD yet.**

That will be the beginning of the next implementation step.

---

# 25. Relationship Between `plan.md` and `implementation.md`

Use the two files differently:

```text
plan.md
   ↓
WHAT are we building?
WHAT are the phases?
WHAT should the final project contain?


implementation.md
   ↓
HOW are we building it?
WHAT files do we create?
WHAT code do we write?
WHAT do we test?
WHAT do we learn?
```

So:

> **`plan.md` = roadmap**

> **`implementation.md` = execution guide**

Both should evolve as the project evolves.
