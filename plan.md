# Wallet Management API — Project Plan

## 1. Project Goal

Build a **Wallet Management REST API using FastAPI** with simple file-based storage.

The main purpose is not to build a production banking system. The purpose is to use one practical project to gain a strong understanding of:

- FastAPI fundamentals
- API routing
- HTTP methods
- Request and response handling
- Pydantic models
- CRUD operations
- Validation
- File operations
- Error handling
- API documentation
- Basic project structure
- Testing
- Integrating a small Machine Learning model

### Important approach

We will **not start with SQLAlchemy or a database**.

For the first version, data will be stored in JSON files. This keeps the project understandable while you learn FastAPI.

Later, if required, the same project can be upgraded to SQLite/SQLAlchemy.

---

# 2. What We Are Building

The application will manage a user's wallet.

A wallet can contain:

- Wallet information
- Current balance
- Income transactions
- Expense transactions
- Transaction history

Example:

```text
Wallet
├── balance: ₹25,000
├── income
│   ├── Salary ₹30,000
│   └── Freelance ₹5,000
└── expenses
    ├── Food ₹2,000
    ├── Travel ₹1,500
    └── Shopping ₹3,500
```

The API will allow us to:

1. Create a wallet
2. View wallet
3. Update wallet
4. Delete wallet
5. Add income
6. Add expense
7. View transactions
8. Update transaction
9. Delete transaction
10. Calculate balance
11. Get spending summaries
12. Use a small ML model for prediction

---

# 3. Suggested Project Structure

Start simple.

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
└── plan.md
```

We will **not create every file at the beginning**.

Files will be introduced only when we need the concept. This is important for learning.

---

# 4. Development Phases

## Phase 1 — FastAPI Foundation

### Goal

Understand how a FastAPI application works.

### Learn

- What FastAPI is
- Creating a FastAPI application
- `FastAPI()`
- Path operations
- GET
- POST
- PUT
- DELETE
- Path parameters
- Query parameters
- Request body
- Automatic Swagger documentation
- Running the server with Uvicorn

### First endpoints

```text
GET /
GET /health
```

Example:

```text
GET /
→ {"message": "Wallet Management API"}
```

### Result

You should be comfortable creating an API and understanding what happens when a request reaches FastAPI.

---

# 5. Phase 2 — Pydantic Models and Validation

### Goal

Learn how FastAPI handles structured input.

Create models such as:

```python
WalletCreate
WalletUpdate
TransactionCreate
TransactionUpdate
```

Example:

```json
{
    "name": "My Wallet",
    "currency": "INR"
}
```

Learn:

- Pydantic `BaseModel`
- Required fields
- Optional fields
- Data types
- Validation
- Response models

### Result

You should understand the difference between:

```text
Raw JSON
    ↓
Pydantic model
    ↓
Validated Python data
    ↓
FastAPI endpoint
```

---

# 6. Phase 3 — File Operations

### Goal

Learn Python file handling before using a database.

We will use JSON files.

Example:

```json
{
    "wallets": []
}
```

Learn:

- `open()`
- Reading files
- Writing files
- JSON
- `json.load()`
- `json.dump()`
- Handling missing files
- Basic helper functions

Create simple functions such as:

```python
read_wallets()
save_wallets()
```

### Result

You should understand how an API can persist data without a database.

---

# 7. Phase 4 — Wallet CRUD

### Goal

Implement the CRUD requested by your TL.

### Endpoints

#### Create wallet

```text
POST /wallets
```

#### Get all wallets

```text
GET /wallets
```

#### Get one wallet

```text
GET /wallets/{wallet_id}
```

#### Update wallet

```text
PUT /wallets/{wallet_id}
```

#### Delete wallet

```text
DELETE /wallets/{wallet_id}
```

### Concepts learned

- CRUD
- Path parameters
- Request bodies
- Response models
- HTTP status codes
- `HTTPException`
- Not-found handling
- IDs

---

# 8. Phase 5 — Transaction Management

This is where the project becomes a real wallet-management application.

### Transaction types

```text
income
expense
```

Example:

```json
{
    "amount": 5000,
    "type": "income",
    "category": "salary",
    "description": "Monthly salary"
}
```

### Endpoints

```text
POST   /wallets/{wallet_id}/transactions
GET    /wallets/{wallet_id}/transactions
GET    /transactions/{transaction_id}
PUT    /transactions/{transaction_id}
DELETE /transactions/{transaction_id}
```

### Business logic

When an income is added:

```text
balance = balance + amount
```

When an expense is added:

```text
balance = balance - amount
```

We will also prevent invalid operations such as:

```text
Expense > available balance
```

if that rule is selected for the project.

### Result

You will learn the difference between:

```text
API layer
    ↓
Business logic
    ↓
File storage
```

---

# 9. Phase 6 — Wallet Summary APIs

Add useful endpoints rather than only basic CRUD.

### Current balance

```text
GET /wallets/{wallet_id}/balance
```

### Transaction summary

```text
GET /wallets/{wallet_id}/summary
```

Possible response:

```json
{
    "balance": 25000,
    "total_income": 40000,
    "total_expense": 15000
}
```

### Category-wise spending

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

This gives you practice with real business logic and data processing.

---

# 10. Phase 7 — Machine Learning Integration

Only after the FastAPI + wallet functionality works.

Do **not** start with ML.

The ML part should be small and understandable.

## Suggested ML Feature

### Expense prediction

Use historical monthly expense data to predict the approximate expense for the next month.

Example:

```text
January    ₹12,000
February   ₹14,000
March      ₹13,500
April      ₹15,000
May        ₹16,000
```

The model predicts:

```text
Next month ≈ ₹16,800
```

### Possible first model

Start with:

```text
Linear Regression
```

Learn:

- Dataset preparation
- Features
- Target
- Train/test split
- Model training
- Prediction
- Saving the model
- Loading the model

The ML model should be called from FastAPI through a service function.

Example:

```text
POST /wallets/{wallet_id}/predict-expense
```

Response:

```json
{
    "predicted_expense": 16800
}
```

### Important

The ML model is a **learning component**, not the main project.

The main project is the FastAPI wallet API.

---

# 11. Phase 8 — Error Handling

Add proper API errors.

Examples:

```text
Wallet not found
Transaction not found
Invalid transaction type
Amount must be greater than zero
Insufficient balance
Invalid wallet ID
```

Learn:

- `HTTPException`
- HTTP status codes
- Validation errors
- Clean error responses

---

# 12. Phase 9 — Testing

Once the API works, test it.

Start with FastAPI's testing tools.

Test:

```text
Create wallet
Get wallet
Update wallet
Delete wallet

Add income
Add expense
Get transactions

Invalid wallet
Invalid transaction
Invalid amount
```

Example flow:

```text
Create Wallet
      ↓
Add Income
      ↓
Check Balance
      ↓
Add Expense
      ↓
Check Balance
      ↓
View Transactions
```

---

# 13. Phase 10 — Documentation

Improve the project so another developer can understand it.

### README should contain

- Project description
- Features
- Technologies
- Installation
- How to run
- API endpoints
- Example requests
- Example responses
- ML feature explanation
- Project structure

FastAPI's automatic Swagger UI will also be used.

Usually:

```text
/docs
```

will provide the interactive API documentation.

---

# 14. Final API Design

The approximate final API will look like this:

```text
GET     /
GET     /health

POST    /wallets
GET     /wallets
GET     /wallets/{wallet_id}
PUT     /wallets/{wallet_id}
DELETE  /wallets/{wallet_id}

POST    /wallets/{wallet_id}/transactions
GET     /wallets/{wallet_id}/transactions

GET     /transactions/{transaction_id}
PUT     /transactions/{transaction_id}
DELETE  /transactions/{transaction_id}

GET     /wallets/{wallet_id}/balance
GET     /wallets/{wallet_id}/summary
GET     /wallets/{wallet_id}/expenses/category

POST    /wallets/{wallet_id}/predict-expense
```

The exact endpoints can be adjusted while building.

---

# 15. Learning Strategy

The most important rule for this project:

> **Do not copy-paste the whole project. Build it concept by concept.**

For every phase:

```text
1. Understand the concept
2. Write a small example
3. Run it
4. Test it
5. Add it to the wallet project
6. Understand why the code works
```

For example, before implementing wallet CRUD:

```text
First learn:
POST request
    ↓
Request body
    ↓
Pydantic model
    ↓
Endpoint
    ↓
Response
```

Then implement it in the project.

---

# 16. What We Will NOT Use Initially

To keep the project beginner-friendly, avoid these at the beginning:

- SQLAlchemy
- PostgreSQL
- Docker
- Authentication/JWT
- Redis
- Celery
- Complex dependency injection
- Advanced architecture
- Microservices

These can be added later if your TL asks for them.

The first goal is:

```text
FastAPI
+
CRUD
+
File Operations
+
Business Logic
+
ML
```

---

# 17. Recommended Technology Stack

```text
Python
FastAPI
Uvicorn
Pydantic
JSON
scikit-learn
pytest
```

Optional later:

```text
SQLite
SQLAlchemy
JWT Authentication
Docker
```

---

# 18. Definition of Done

The project is considered complete when:

- [ ] FastAPI application runs successfully
- [ ] Swagger documentation works
- [ ] Wallet CRUD works
- [ ] Data persists in JSON files
- [ ] Transactions can be created
- [ ] Income changes balance correctly
- [ ] Expenses change balance correctly
- [ ] Transaction CRUD works
- [ ] Wallet summary works
- [ ] Category-wise expenses work
- [ ] Errors are handled properly
- [ ] ML model can predict future expense
- [ ] ML prediction is exposed through an API
- [ ] Basic tests pass
- [ ] README is complete
- [ ] Project can be explained clearly to the TL

---

# 19. Phase-by-Phase Learning Checklist

| Phase | Main Topic | Expected Understanding |
|---|---|---|
| 1 | FastAPI basics | Can create and run APIs |
| 2 | Pydantic | Can validate request/response data |
| 3 | File operations | Can read/write JSON data |
| 4 | CRUD | Can build complete CRUD APIs |
| 5 | Transactions | Can implement business logic |
| 6 | Summaries | Can process and return useful data |
| 7 | ML | Can integrate a trained model |
| 8 | Errors | Can handle invalid requests |
| 9 | Testing | Can verify API behavior |
| 10 | Documentation | Can present the project professionally |

---

# 20. Our Working Method

We will build this **one phase at a time**.

At each phase I should explain:

1. What we are learning
2. Why we need it
3. The minimum code required
4. How to run it
5. How to test it
6. What output to expect
7. What each important line means
8. A small task for you to try yourself

Only after you understand the current phase should we move to the next one.

---

# Final Project Concept

```text
                    WALLET MANAGEMENT API
                            │
             ┌──────────────┴──────────────┐
             │                             │
        FASTAPI API                  MACHINE LEARNING
             │                             │
      ┌──────┼──────┐                 Expense Prediction
      │      │      │
    Wallet  CRUD  Transactions
      │             │
      │        ┌────┴────┐
      │      Income    Expense
      │        │          │
      └────────┴──────────┘
                 │
          Business Logic
                 │
            JSON Files
```

**Core objective:** Build a useful wallet API while learning FastAPI properly, rather than simply finishing a CRUD assignment.
