# Product Requirements Document (PRD)
# Wallet Management API

## 1. Document Overview

| Field | Details |
|---|---|
| Product | Wallet Management API |
| Version | 1.0 |
| Status | Development |
| Primary Technology | FastAPI |
| Storage | JSON files |
| ML Component | Expense prediction |
| Primary Purpose | FastAPI learning project with practical wallet functionality |

---

# 2. Product Vision

Build a simple **Wallet Management REST API** that allows users to manage wallets, record income and expenses, view transaction history, calculate balances, generate spending summaries, and receive an approximate prediction of future expenses.

The application is primarily a **learning project**. It should provide enough real-world functionality to practice FastAPI concepts without introducing unnecessary complexity.

The first version will use **JSON file storage instead of a database**.

---

# 3. Problem Statement

A basic CRUD example is useful for learning individual API operations, but it does not provide enough practical context for understanding how a real API is structured.

This project solves that learning problem by combining:

```text
FastAPI
+
CRUD
+
Pydantic validation
+
File operations
+
Business logic
+
Machine Learning
```

The wallet domain gives us a practical reason to use each of these concepts.

---

# 4. Goals

## Primary Goals

1. Learn FastAPI through a complete practical project.
2. Implement complete CRUD operations.
3. Learn request and response validation using Pydantic.
4. Learn file-based data persistence using JSON.
5. Implement wallet and transaction business logic.
6. Implement balance calculation.
7. Implement useful summary APIs.
8. Integrate a simple Machine Learning model.
9. Learn basic API testing.
10. Produce a project that can be clearly explained to the team lead.

## Learning Goals

By the end of the project, the developer should understand:

- FastAPI application creation
- Routing
- HTTP methods
- Path parameters
- Query parameters
- Request bodies
- Pydantic models
- Response models
- HTTP status codes
- Error handling
- File operations
- JSON serialization/deserialization
- Basic API architecture
- API testing
- ML model integration

---

# 5. Non-Goals

The initial version will **not** attempt to build a production-grade financial platform.

The following are intentionally excluded from the first version:

- SQLAlchemy
- PostgreSQL
- Complex database architecture
- Authentication/JWT
- Redis
- Celery
- Docker
- Microservices
- Payment gateway integration
- Real bank integration
- Financial transaction processing
- Complex ML systems

These may be considered in a future version if required.

---

# 6. Target User

The first version is intended for:

### Primary User

A developer/student learning FastAPI and backend development.

### Application-Level User

A person who wants to maintain simple wallet and personal expense records.

---

# 7. Core Features

## 7.1 Wallet Management

Users should be able to:

- Create a wallet
- View all wallets
- View a specific wallet
- Update wallet information
- Delete a wallet
- View current balance

---

## 7.2 Transaction Management

Users should be able to:

- Add income
- Add expenses
- View wallet transactions
- View a specific transaction
- Update a transaction
- Delete a transaction

Supported transaction types:

```text
income
expense
```

---

## 7.3 Balance Management

The wallet balance should change according to transactions.

For income:

```text
new balance = current balance + income
```

For expense:

```text
new balance = current balance - expense
```

The application should prevent an expense from exceeding the available balance if that business rule is enabled in the implementation.

---

## 7.4 Spending Summary

Users should be able to see:

- Total income
- Total expenses
- Current balance
- Category-wise expenses

Example:

```json
{
    "balance": 25000,
    "total_income": 40000,
    "total_expense": 15000
}
```

Category example:

```json
{
    "food": 3000,
    "travel": 2000,
    "shopping": 5000
}
```

---

## 7.5 Expense Prediction

The application should provide an approximate prediction of future expenses based on historical expense data.

The first ML implementation will use:

```text
Linear Regression
```

Example:

```text
Historical monthly expenses
        ↓
ML model
        ↓
Predicted next-month expense
```

Example response:

```json
{
    "wallet_id": 1,
    "predicted_expense": 16800
}
```

The prediction feature is intended for learning and demonstration and should not be treated as financial advice.

---

# 8. Functional Requirements

## FR-01 — Application Health

The API must provide a basic health endpoint.

```text
GET /health
```

Expected response:

```json
{
    "status": "healthy"
}
```

---

## FR-02 — Create Wallet

The API must allow creation of a wallet.

```text
POST /wallets
```

Input example:

```json
{
    "name": "My Wallet",
    "currency": "INR"
}
```

The system should:

1. Validate the request.
2. Generate a wallet ID.
3. Set the initial balance.
4. Store the wallet.
5. Return the created wallet.

---

## FR-03 — Retrieve Wallets

Retrieve all wallets.

```text
GET /wallets
```

---

## FR-04 — Retrieve a Single Wallet

Retrieve a wallet using its ID.

```text
GET /wallets/{wallet_id}
```

If the wallet does not exist:

```text
HTTP 404
```

---

## FR-05 — Update Wallet

Update wallet information.

```text
PUT /wallets/{wallet_id}
```

Possible fields:

```text
name
currency
```

The balance should not be arbitrarily changed through the normal wallet update endpoint.

---

## FR-06 — Delete Wallet

Delete a wallet.

```text
DELETE /wallets/{wallet_id}
```

The implementation should define how associated transactions are handled.

For the learning version, this behavior should be kept simple and documented.

---

## FR-07 — Create Transaction

Add a transaction to a wallet.

```text
POST /wallets/{wallet_id}/transactions
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

The system must:

1. Verify the wallet exists.
2. Validate the transaction.
3. Generate a transaction ID.
4. Store the transaction.
5. Update the wallet balance.
6. Return the transaction.

---

## FR-08 — Retrieve Transactions

Retrieve transactions belonging to a wallet.

```text
GET /wallets/{wallet_id}/transactions
```

---

## FR-09 — Retrieve Transaction

Retrieve a specific transaction.

```text
GET /transactions/{transaction_id}
```

If it does not exist:

```text
HTTP 404
```

---

## FR-10 — Update Transaction

Update an existing transaction.

```text
PUT /transactions/{transaction_id}
```

Because a transaction affects wallet balance, updating a transaction must correctly reverse the old financial effect and apply the new effect.

Example:

```text
Old expense = ₹2,000
New expense = ₹3,000
```

The balance should change by:

```text
-₹1,000
```

rather than subtracting the entire new amount again.

---

## FR-11 — Delete Transaction

Delete a transaction.

```text
DELETE /transactions/{transaction_id}
```

The wallet balance must be corrected when a transaction is deleted.

Example:

```text
Balance = ₹8,000
Existing expense = ₹2,000

Delete expense
        ↓
Balance = ₹10,000
```

---

## FR-12 — Get Balance

```text
GET /wallets/{wallet_id}/balance
```

Example response:

```json
{
    "wallet_id": 1,
    "balance": 25000
}
```

---

## FR-13 — Get Summary

```text
GET /wallets/{wallet_id}/summary
```

The response should include:

```text
total_income
total_expense
balance
```

---

## FR-14 — Category-wise Expenses

```text
GET /wallets/{wallet_id}/expenses/category
```

The API should group expense transactions by category.

---

## FR-15 — Expense Prediction

```text
POST /wallets/{wallet_id}/predict-expense
```

The API should use historical expense information to produce an approximate future expense prediction.

---

# 9. API Requirements

The approximate API surface is:

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

The exact API design may be adjusted during implementation if a simpler or more consistent design is discovered.

---

# 10. Data Requirements

## Wallet

Initial wallet structure:

```json
{
    "id": 1,
    "name": "My Wallet",
    "currency": "INR",
    "balance": 0
}
```

## Transaction

Initial transaction structure:

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

---

# 11. Storage Requirements

The initial version will use JSON files.

```text
app/data/wallets.json
app/data/transactions.json
```

The application should support:

```text
Read JSON
    ↓
Convert to Python data
    ↓
Perform operation
    ↓
Convert back to JSON
    ↓
Write JSON
```

A database is intentionally postponed to keep the learning curve manageable.

---

# 12. Validation Requirements

The API should validate:

- Required fields
- Data types
- Positive transaction amounts
- Valid transaction type
- Valid wallet IDs
- Existing transactions
- Existing wallets

Example invalid transaction:

```json
{
    "amount": -500,
    "type": "expense",
    "category": "food"
}
```

This should be rejected.

---

# 13. Error Requirements

The API should return meaningful HTTP errors.

Examples:

| Situation | Status |
|---|---:|
| Resource found | 200 |
| Resource created | 201 |
| Resource deleted successfully | 200/204 |
| Invalid request | 400 |
| Resource not found | 404 |
| Validation failure | 422 |

Example:

```json
{
    "detail": "Wallet not found"
}
```

---

# 14. ML Requirements

## Model

Initial model:

```text
Linear Regression
```

## Input

Historical monthly expense data.

Example:

```text
Month 1 → ₹12,000
Month 2 → ₹14,000
Month 3 → ₹13,500
Month 4 → ₹15,000
Month 5 → ₹16,000
```

## Output

Approximate future expense.

The model should be:

1. Trained separately.
2. Saved to a model file.
3. Loaded by the FastAPI application.
4. Used through a prediction service.
5. Exposed through an API endpoint.

---

# 15. Architecture Requirements

The application should gradually evolve toward:

```text
Client
  ↓
FastAPI Router
  ↓
Pydantic Schema
  ↓
Service / Business Logic
  ↓
JSON File Storage
```

For ML:

```text
FastAPI Router
      ↓
Prediction Service
      ↓
ML Model
      ↓
Prediction
```

The architecture should remain simple enough for a beginner to understand.

---

# 16. Non-Functional Requirements

## NFR-01 — Simplicity

The implementation should avoid unnecessary technologies and abstractions.

## NFR-02 — Understandability

Code should be readable and explainable by the developer.

## NFR-03 — Maintainability

Related functionality should eventually be separated into routers, schemas, and services.

## NFR-04 — Documentation

FastAPI's automatic OpenAPI/Swagger documentation should be available.

Expected URL:

```text
/docs
```

## NFR-05 — Reliability

Invalid requests should not silently corrupt wallet or transaction data.

## NFR-06 — Testability

Core CRUD and transaction behavior should be testable using automated tests.

---

# 17. User Stories

### Wallet

> As a user, I want to create a wallet so that I can track my money.

> As a user, I want to view my wallet so that I know my current balance.

> As a user, I want to update my wallet information.

> As a user, I want to delete a wallet.

### Transactions

> As a user, I want to record income so that my wallet balance increases.

> As a user, I want to record expenses so that my wallet balance decreases.

> As a user, I want to see transaction history.

> As a user, I want to update or delete an incorrect transaction.

### Analytics

> As a user, I want to see my total income and expenses.

> As a user, I want to see spending by category.

### Prediction

> As a user, I want an approximate prediction of my next month's expenses based on historical data.

---

# 18. Example User Journey

```text
Create Wallet
     ↓
Wallet created with ₹0
     ↓
Add Salary ₹30,000
     ↓
Balance = ₹30,000
     ↓
Add Food Expense ₹2,000
     ↓
Balance = ₹28,000
     ↓
Add Travel Expense ₹1,500
     ↓
Balance = ₹26,500
     ↓
View Summary
     ↓
View Category Expenses
     ↓
Predict Next Month Expense
```

---

# 19. Development Milestones

## Milestone 1

FastAPI application runs.

```text
GET /
GET /health
```

## Milestone 2

Pydantic request/response models work.

## Milestone 3

JSON file storage works.

## Milestone 4

Wallet CRUD works.

## Milestone 5

Transaction CRUD works.

## Milestone 6

Balance and summary logic works.

## Milestone 7

ML model works independently.

## Milestone 8

ML model is integrated with FastAPI.

## Milestone 9

Tests pass.

## Milestone 10

Documentation is complete.

---

# 20. Definition of Done

The product is complete when:

- [ ] FastAPI application starts successfully.
- [ ] `/docs` works.
- [ ] Wallet CRUD works.
- [ ] Wallet data persists in JSON.
- [ ] Transaction CRUD works.
- [ ] Income updates balance correctly.
- [ ] Expense updates balance correctly.
- [ ] Updating a transaction correctly adjusts balance.
- [ ] Deleting a transaction correctly adjusts balance.
- [ ] Summary endpoint works.
- [ ] Category-wise expense endpoint works.
- [ ] Validation works.
- [ ] Errors are handled correctly.
- [ ] ML model is trained.
- [ ] ML model can be loaded by the API.
- [ ] Expense prediction endpoint works.
- [ ] Core API tests pass.
- [ ] README explains the project.
- [ ] The developer can explain the implementation to the TL.

---

# 21. Future Enhancements

Only after the first version is understood, the project can be extended with:

```text
SQLite
    ↓
SQLAlchemy
    ↓
Authentication
    ↓
JWT
    ↓
Docker
    ↓
PostgreSQL
```

Other possible features:

- Multiple users
- Budget limits
- Monthly reports
- Date-based filtering
- Better ML features
- Expense charts
- Authentication
- Database migration

These are **future possibilities**, not requirements for version 1.

---

# 22. Success Criteria

The project succeeds if the developer can demonstrate both:

### Functional understanding

```text
"I built a working wallet management API."
```

and:

### Technical understanding

```text
"I understand why FastAPI routes, Pydantic models,
services, file operations, validation, and ML integration
are used and how they interact."
```

The second outcome is the most important goal of this project.
