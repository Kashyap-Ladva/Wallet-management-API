# Wallet Management API — Next-Level Implementation Guide

## 1. Purpose

This document is the execution guide for the five-phase wallet-management upgrade.

The existing project already has:

- FastAPI application
- routers
- services
- Pydantic schemas
- SQLAlchemy models
- PostgreSQL database setup
- User → Super Wallet → Mini Wallet → Transaction relationships

The old implementation used a simpler wallet/transaction CRUD architecture. This guide replaces that roadmap with the new five-phase implementation sequence.

The current model has a one-to-one user/super-wallet relationship through a unique `user_id`, one-to-many mini wallets, and transactions connected to both wallet levels. fileciteturn1file0L20-L55

---

# 2. Target Project Structure

Build toward:

```text
wallet-management/
│
├── app/
│   ├── main.py
│   │
│   ├── database.py
│   ├── models.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── dependencies.py
│   │
│   ├── routers/
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── super_wallet.py
│   │   ├── mini_wallets.py
│   │   ├── transactions.py
│   │   ├── analytics.py
│   │   ├── budgets.py
│   │   ├── imports.py
│   │   ├── savings.py
│   │   ├── investments.py
│   │   ├── debts.py
│   │   └── recurring_payments.py
│   │
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── super_wallet.py
│   │   ├── mini_wallet.py
│   │   ├── transaction.py
│   │   ├── analytics.py
│   │   ├── budget.py
│   │   ├── import.py
│   │   ├── savings.py
│   │   ├── investment.py
│   │   ├── debt.py
│   │   └── recurring_payment.py
│   │
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── wallet_service.py
│   │   ├── transaction_service.py
│   │   ├── analytics_service.py
│   │   ├── budget_service.py
│   │   ├── import_service.py
│   │   ├── proof_service.py
│   │   ├── savings_service.py
│   │   ├── investment_service.py
│   │   ├── debt_service.py
│   │   └── recurring_payment_service.py
│   │
│   └── jobs/
│       ├── daily_summary.py
│       └── monthly_reminders.py
│
├── tests/
│   ├── test_auth.py
│   ├── test_wallets.py
│   ├── test_transactions.py
│   ├── test_analytics.py
│   ├── test_budgets.py
│   ├── test_imports.py
│   └── test_financial_integrity.py
│
├── .env
├── .gitignore
├── requirements.txt
├── README.md
├── plan.md
└── implementation.md
```

Do not create all files at once. Add them when the phase needs them.

---

# 3. Architectural Rule

Use this flow consistently:

```text
HTTP Request
     ↓
Router
     ↓
Schema validation
     ↓
Authentication / ownership
     ↓
Service
     ↓
SQLAlchemy
     ↓
PostgreSQL
     ↓
Service result
     ↓
Response schema
     ↓
HTTP Response
```

Routers should handle HTTP concerns.

Services should contain business rules.

SQLAlchemy should handle database interaction.

---

# PHASE 1 — Authentication & Wallet Foundation

## Step 1 — Authentication model review

The current `User` schema has name, phone, email, currency and date, but no password field. fileciteturn0file3L4-L9

Do not expose a password field in `UserResponse`.

Add the minimum authentication data required by the chosen auth design, for example:

```text
password_hash
```

If token/session persistence is required by the final authentication architecture, add the required supporting model/table.

Do not store:

```text
password
```

as plaintext.

---

## Step 2 — Security module

Create:

```text
app/core/security.py
```

Responsibilities:

```text
hash_password(password)
verify_password(password, password_hash)
create_access_token(user_id)
decode_access_token(token)
```

Keep JWT/token code separate from router code.

---

## Step 3 — Authentication dependencies

Create:

```text
app/core/dependencies.py
```

Main dependency:

```text
get_current_user()
```

Flow:

```text
Authorization header
       ↓
Bearer token
       ↓
Decode token
       ↓
Extract user ID
       ↓
Load User
       ↓
Return current_user
```

Every protected wallet/transaction route should use this dependency.

---

## Step 4 — Auth router

Create:

```text
app/routers/auth.py
```

Endpoints:

```text
POST /auth/register
POST /auth/login
```

Registration:

```text
Request
 ↓
Validate email/phone/etc.
 ↓
Check existing user
 ↓
Hash password
 ↓
Create User
 ↓
Commit
 ↓
Return safe response
```

Login:

```text
Request
 ↓
Find user
 ↓
Verify password
 ↓
Create token
 ↓
Return token
```

Never return the password hash to the client.

---

## Step 5 — User router

Create:

```text
app/routers/users.py
```

Endpoints:

```text
GET /users/me
PUT /users/me
```

Use:

```python
current_user = Depends(get_current_user)
```

Do not accept `user_id` from the client for `/users/me`.

---

## Step 6 — Super wallet ownership

Create/update:

```text
app/routers/super_wallet.py
app/services/wallet_service.py
```

Create:

```text
POST /super-wallet
```

Before creation:

```text
current_user
     ↓
Check existing wallet
     ↓
exists → reject
doesn't exist → create
```

The current SQLAlchemy model already has a unique constraint on `wallets.user_id`, so the database also protects the one-super-wallet rule. fileciteturn1file0L33-L40

---

## Step 7 — Mini wallet CRUD

Create:

```text
app/routers/mini_wallets.py
```

Endpoints:

```text
POST   /super-wallet/mini-wallets
GET    /super-wallet/mini-wallets
GET    /mini-wallets/{mini_wallet_id}
PUT    /mini-wallets/{mini_wallet_id}
DELETE /mini-wallets/{mini_wallet_id}
```

Ownership flow:

```text
current_user
    ↓
get super wallet
    ↓
get mini wallet
    ↓
verify mini_wallet.super_wallet_id
    ↓
allow operation
```

Never trust a client-supplied wallet ID without checking ownership.

---

## Phase 1 testing

Test:

```text
Register user
Login
Access /users/me
Create super wallet
Create second super wallet → must fail
Create mini wallet
Read mini wallet
Update mini wallet
Delete mini wallet
User A accesses User B wallet → must fail
No token → protected endpoint must fail
```

Phase 1 is complete only when the authorization boundary is reliable.

---

# PHASE 2 — Transaction Engine

## Step 1 — Transaction schemas

The current transaction schema already contains:

```text
amount
type
category
description
date_created
modeofpayment
proof
```

and limits type to `income` or `expense` with a positive amount. fileciteturn1file1L8-L25

Keep the existing structure unless a new requirement requires a change.

Add specialized schemas when useful:

```text
TransactionCreate
TransactionUpdate
TransactionResponse
TransactionFilter
TransactionHistoryResponse
```

---

## Step 2 — Create transaction service

Use:

```text
app/services/transaction_service.py
```

Main responsibilities:

```text
create_transaction()
get_transaction()
list_transactions()
update_transaction()
delete_transaction()
```

Do not put the financial mutation logic directly into routers.

---

## Step 3 — Create transaction

Endpoint:

```text
POST /mini-wallets/{mini_wallet_id}/transactions
```

Flow:

```text
Request
  ↓
Validate current user
  ↓
Find mini wallet
  ↓
Verify ownership
  ↓
Validate transaction
  ↓
Create transaction
  ↓
Commit
  ↓
Return response
```

---

## Step 4 — Balance calculation

Current model behavior:

```text
Mini Wallet Balance
=
sum(income)
-
sum(expense)
```

and:

```text
Super Wallet Balance
=
sum(mini wallet balances)
```

This is already represented by model properties. fileciteturn1file0L58-L60 fileciteturn1file0L83-L94

For the first implementation, keep transaction data as the source of truth.

For high-volume optimization later, consider persisted/cached balances maintained atomically.

---

## Step 5 — Transaction update

This is a critical operation.

Algorithm:

```text
Load old transaction
        ↓
Calculate old financial effect
        ↓
Reverse old effect
        ↓
Apply new transaction values
        ↓
Apply new financial effect
        ↓
Commit
```

Financial effect:

```text
income  → +amount
expense → -amount
```

Example:

```text
Old = expense 2000
New = expense 3000

Reverse old = +2000
Apply new   = -3000

Net change = -1000
```

If type changes:

```text
income → expense
```

reverse the income and apply the expense.

---

## Step 6 — Transaction delete

Flow:

```text
Load transaction
      ↓
Reverse its financial effect
      ↓
Delete transaction
      ↓
Commit
```

This prevents balance corruption.

---

## Step 7 — Database transaction/rollback

Financial operations must be atomic.

Use:

```text
session.begin()
```

or an equivalent SQLAlchemy transaction pattern.

Concept:

```text
BEGIN
  create/update/delete transaction
  update related financial state
COMMIT
```

If anything fails:

```text
ROLLBACK
```

Never leave half of a financial operation committed.

---

## Step 8 — Transaction history

Endpoints:

```text
GET /super-wallet/transactions
GET /mini-wallets/{mini_wallet_id}/transactions
GET /transactions/{transaction_id}
```

Filters:

```text
date_from
date_to
type
category
modeofpayment
mini_wallet_id
```

Add pagination:

```text
limit
offset
```

later replace with cursor pagination if necessary.

---

## Step 9 — Proof

Create:

```text
app/services/proof_service.py
```

Support:

```text
text proof
image proof
```

Recommended flow:

```text
Upload image
   ↓
Validate MIME type
   ↓
Validate file size
   ↓
Generate safe storage key
   ↓
Store file
   ↓
Store key/URL in transaction.proof
```

Do not use user-provided filenames directly as storage paths.

---

## Phase 2 testing

Test:

```text
Income
Expense
Income balance
Expense balance
Update amount
Update type
Update mini wallet
Delete transaction
Historical date
Future date if allowed
Category
Payment mode
Proof
Insufficient balance rule if enabled
Cross-user access
Rollback after failed operation
```

---

# PHASE 3 — Analytics & Budgets

## Step 1 — Analytics schemas

Create:

```text
app/schemas/analytics.py
```

Possible response schemas:

```text
DailySummary
MonthlySummary
YearlySummary
CategorySummary
MiniWalletSummary
ChartData
```

---

## Step 2 — Analytics service

Create:

```text
app/services/analytics_service.py
```

Do not fetch every transaction into Python for every analytics request.

Prefer SQL aggregation:

```text
SUM
COUNT
GROUP BY
DATE filtering
```

This becomes important as the database grows.

---

## Step 3 — Daily analytics

Endpoint:

```text
GET /analytics/daily
```

Parameters:

```text
date
```

Return:

```text
income
expense
net
transaction_count
category_breakdown
mini_wallet_breakdown
```

---

## Step 4 — Monthly analytics

Endpoint:

```text
GET /analytics/monthly
```

Parameters:

```text
year
month
```

Return:

```text
total_income
total_expense
net
categories
mini_wallets
```

---

## Step 5 — Yearly analytics

Endpoint:

```text
GET /analytics/yearly
```

Parameter:

```text
year
```

Return monthly values:

```text
January
February
...
December
```

---

## Step 6 — Mini-wallet comparison

Endpoint:

```text
GET /analytics/mini-wallets
```

Query:

```text
GROUP BY mini_wallet_id
SUM expense
```

Return chart-friendly data.

---

## Step 7 — Category comparison

Endpoint:

```text
GET /analytics/categories
```

Query:

```text
WHERE type = 'expense'
GROUP BY category
SUM amount
```

---

## Step 8 — Pie chart

Endpoint:

```text
GET /analytics/expenses/pie
```

Return:

```json
{
  "labels": ["Food", "Travel", "Rent"],
  "values": [8000, 5000, 12000]
}
```

The backend should provide data, not render the actual chart.

---

## Step 9 — Bar chart

Endpoint:

```text
GET /analytics/expenses/bar
```

Return:

```json
{
  "labels": ["Jan", "Feb", "Mar"],
  "values": [12000, 14000, 11000]
}
```

---

## Step 10 — Budget/target system

Create:

```text
app/routers/budgets.py
app/services/budget_service.py
app/schemas/budget.py
```

Support:

```text
daily
monthly
```

Target flow:

```text
Create target
     ↓
Store target
     ↓
Calculate spending for target period
     ↓
Compare
     ↓
Return status
```

Response:

```text
target
spent
remaining
percentage_used
exceeded
```

---

## Phase 3 testing

Use controlled transaction fixtures.

Example:

```text
Food = 3000
Travel = 2000
Rent = 10000
```

Verify:

```text
Daily totals
Monthly totals
Yearly totals
Category totals
Mini-wallet totals
Chart data
Budget status
```

---

# PHASE 4 — Import, Savings, Debt & Automation

## A. Excel Import

### Step 1 — Dependencies

Add an Excel-reading dependency such as:

```text
openpyxl
```

If using pandas for import processing:

```text
pandas
openpyxl
```

Do not add unnecessary libraries.

### Step 2 — Import router

Create:

```text
app/routers/imports.py
```

Endpoints:

```text
POST /imports/excel/preview
POST /imports/excel/confirm
```

### Step 3 — Import service

Create:

```text
app/services/import_service.py
```

Flow:

```text
Upload
 ↓
Extension/MIME validation
 ↓
Read workbook
 ↓
Check required columns
 ↓
Normalize rows
 ↓
Validate each row
 ↓
Build preview
 ↓
User confirms
 ↓
DB transaction
 ↓
Insert valid transactions
```

Required import columns should be explicitly defined, for example:

```text
amount
type
category
date_created
modeofpayment
description
```

Do not silently guess column meanings.

### Step 4 — Duplicate handling

Define a duplicate strategy before implementation.

Possible approaches:

```text
reject duplicates
skip duplicates
import duplicates
```

The chosen behavior should be explicit in the API contract.

---

# B. Savings

If the current schema does not already contain savings entities, add them before implementing the feature.

Create:

```text
savings.py
savings_service.py
savings.py router
```

Suggested fields:

```text
id
user_id
name
target_amount
current_amount
created_at
target_date
status
```

Operations:

```text
Create goal
Add contribution
Withdraw/reduce
View progress
Update goal
Delete goal
```

---

# C. Investments

Create a separate investment domain.

Suggested operations:

```text
POST /investments
GET /investments
GET /investments/{id}
PUT /investments/{id}
DELETE /investments/{id}
```

Keep investment records separate from ordinary transaction categories unless product rules define otherwise.

---

# D. Debt / Credit

Create:

```text
app/routers/debts.py
app/services/debt_service.py
app/schemas/debt.py
```

Model concepts:

```text
direction:
  lent
  borrowed

person
amount
remaining_amount
date
due_date
status
notes
```

Flow:

```text
Create debt/credit
      ↓
Track outstanding amount
      ↓
Record repayment
      ↓
Update remaining amount
      ↓
Mark settled
```

---

# E. Recurring payments

Create:

```text
app/routers/recurring_payments.py
app/services/recurring_payment_service.py
app/schemas/recurring_payment.py
```

Fields:

```text
name
amount
category
due_day
frequency
active
```

---

# F. Daily summary job

Create:

```text
app/jobs/daily_summary.py
```

Logic:

```text
Get users
   ↓
For each user
   ↓
Get today's transactions
   ↓
Calculate summary
   ↓
Calculate budget status
   ↓
Generate message
   ↓
Send/store notification
```

Keep summary generation separate from delivery.

---

# G. Monthly reminder job

Create:

```text
app/jobs/monthly_reminders.py
```

Flow:

```text
Scheduler
   ↓
Find active recurring payments
   ↓
Find payments relevant to the new month
   ↓
Create reminders
   ↓
Deliver/store reminder
```

Do not directly mix scheduler logic with database business logic.

---

# PHASE 5 — Testing & Production Hardening

## Step 1 — Unit tests

Test pure business functions:

```text
balance calculation
transaction effect
budget calculation
category aggregation
date-range filtering
debt remaining amount
```

---

## Step 2 — API tests

Use FastAPI test client.

Test:

```text
register
login
authenticated request
unauthenticated request
wrong token
cross-user access
```

---

## Step 3 — Financial integrity tests

These are mandatory.

Example:

```text
Starting balance = 0

+ income 10000
= 10000

- expense 2000
= 8000

Update expense 2000 → 3000
= 7000

Delete expense
= 10000
```

Also test:

```text
income → expense
expense → income
mini wallet change
failed transaction rollback
```

---

## Step 4 — Pagination

Transaction endpoints should not return an unlimited number of records.

Example:

```text
GET /super-wallet/transactions?limit=50&offset=0
```

---

## Step 5 — Database indexes

Review actual query patterns.

Likely candidates:

```text
users.email
transactions.mini_wallet_id
transactions.super_wallet_id
transactions.date_created
transactions.category
transactions.type
```

Do not add every possible index automatically.

---

## Step 6 — Configuration

Use `.env` for:

```text
DATABASE_URL
JWT_SECRET
JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
FILE_STORAGE_PATH
```

Never commit secrets.

---

## Step 7 — Logging

Add useful structured logs around:

```text
authentication failures
transaction creation/update/delete
import failures
scheduler failures
unexpected exceptions
```

Do not log passwords, tokens, or sensitive proof content.

---

## Step 8 — Global error handling

Create consistent API errors.

Example:

```json
{
  "detail": "Transaction not found"
}
```

For validation/business errors, use appropriate HTTP status codes consistently.

---

## Step 9 — Docker

Only after the application works outside Docker.

Target:

```text
FastAPI container
       ↓
PostgreSQL container
```

Use environment variables for the DB connection.

---

# 4. API Grouping

Final API organization:

```text
/auth
/users

/super-wallet
/mini-wallets

/transactions

/analytics
/budgets

/imports

/savings
/investments
/debts
/recurring-payments
```

Keep route naming consistent.

---

# 5. Critical End-to-End Flows

## Flow A — New user

```text
Register
 ↓
Password hashed
 ↓
User created
 ↓
Login
 ↓
Token
 ↓
Create Super Wallet
 ↓
Create Mini Wallets
```

## Flow B — Expense

```text
Authenticated request
 ↓
Mini wallet ID
 ↓
Ownership check
 ↓
Transaction validation
 ↓
Create expense
 ↓
Commit
 ↓
Mini balance reflects expense
 ↓
Super balance reflects expense
```

## Flow C — Transaction update

```text
Request
 ↓
Load old transaction
 ↓
Reverse old effect
 ↓
Validate new values
 ↓
Apply new effect
 ↓
Commit
```

## Flow D — Analytics

```text
Request
 ↓
Authenticate
 ↓
Build date range
 ↓
SQL aggregation
 ↓
Analytics service
 ↓
Response schema
 ↓
Chart-ready JSON
```

## Flow E — Excel

```text
Excel upload
 ↓
Validate
 ↓
Preview
 ↓
Confirm
 ↓
DB transaction
 ↓
Insert transactions
 ↓
Commit / rollback
```

## Flow F — Daily summary

```text
Scheduler
 ↓
Today's transactions
 ↓
Analytics service
 ↓
Budget service
 ↓
Summary generator
 ↓
Notification/storage
```

---

# 6. Implementation Order Checklist

## Phase 1

```text
[ ] Add authentication fields/model support
[ ] Password hashing
[ ] JWT/access token
[ ] Register
[ ] Login
[ ] Current-user dependency
[ ] User profile
[ ] Super wallet
[ ] One-wallet enforcement
[ ] Mini wallet CRUD
[ ] Ownership checks
[ ] Phase 1 tests
```

## Phase 2

```text
[ ] Transaction create
[ ] Income
[ ] Expense
[ ] Balance logic
[ ] Transaction update
[ ] Transaction delete
[ ] Transaction history
[ ] Filters
[ ] Pagination
[ ] Proof upload/reference
[ ] Atomic financial operations
[ ] Phase 2 tests
```

## Phase 3

```text
[ ] Daily analytics
[ ] Monthly analytics
[ ] Yearly analytics
[ ] Mini-wallet comparison
[ ] Category comparison
[ ] Pie-chart API
[ ] Bar-chart API
[ ] Daily target
[ ] Monthly target
[ ] Target status
[ ] Phase 3 tests
```

## Phase 4

```text
[x] Excel preview
[x] Excel validation
[x] Excel import
[x] Duplicate strategy
[x] Savings
[x] Investments
[x] Debt/credit
[x] Recurring payments
[x] Daily summary
[x] Monthly reminders
[x] Phase 4 tests
```

## Phase 5

```text
[ ] Unit tests
[ ] API tests
[ ] Financial integrity tests
[ ] Authorization tests
[ ] Database integration tests
[ ] Index review
[ ] Pagination review
[ ] Logging
[ ] Error handling
[ ] Security review
[ ] Docker
[ ] Deployment configuration
[ ] Final README
```

---

# 7. Important Rules

## Rule 1 — Do not put business logic in routers

Bad:

```text
Router
  ├── database queries
  ├── balance calculations
  ├── validation
  └── business rules
```

Good:

```text
Router
  ↓
Service
  ↓
Database
```

---

## Rule 2 — Never trust IDs from the client

Bad:

```text
GET /mini-wallets/55
```

and immediately returning wallet 55.

Good:

```text
current_user
 ↓
super wallet owned by user
 ↓
mini wallet 55 belongs to super wallet?
 ↓
allow/reject
```

---

## Rule 3 — Financial mutations must be atomic

Do not allow:

```text
transaction inserted
but
balance update failed
```

or:

```text
balance changed
but
transaction insert failed
```

Use a database transaction.

---

## Rule 4 — Transactions are the financial source of truth

Do not allow random APIs to directly modify balances.

Use:

```text
Transaction
    ↓
Financial effect
    ↓
Balance
```

rather than:

```text
Random balance update
```

---

## Rule 5 — Dates are first-class data

Every transaction must retain its original timestamp/date.

Analytics should filter by the transaction date rather than the date on which the API was called.

---

## Rule 6 — Backend returns chart data

The backend should return:

```text
labels
values
series
```

The frontend/client renders:

```text
pie chart
bar chart
line chart
```

---

# 8. First Task to Implement Now

Do not begin all five phases together.

Start here:

```text
PHASE 1
   ↓
Authentication foundation
   ↓
User ownership
   ↓
Super wallet
   ↓
Mini wallet
```

Immediate implementation sequence:

```text
1. Update User model/schema for authentication.
2. Create security.py.
3. Implement password hashing.
4. Implement token creation/verification.
5. Implement POST /auth/register.
6. Implement POST /auth/login.
7. Implement get_current_user dependency.
8. Protect wallet routes.
9. Implement one-super-wallet rule.
10. Implement mini-wallet CRUD.
11. Test user isolation.
```

Only after this passes should you start the transaction engine.

---

# 9. Definition of Done for Each Phase

Every phase follows:

```text
Design
  ↓
Schema review
  ↓
Service implementation
  ↓
Router implementation
  ↓
Database integration
  ↓
Manual Swagger/Postman testing
  ↓
Automated tests
  ↓
Error cases
  ↓
Phase complete
```

Do not move forward simply because the happy path works.

---

# 10. Final Development Philosophy

The original project already established the separation:

```text
Router
 ↓
Schema
 ↓
Service
 ↓
SQLAlchemy ORM
 ↓
Database
```

The new system should preserve that separation while expanding the domains. The previous project documentation also defines routers as request handlers, schemas as validation, services as business logic, and SQLAlchemy as the ORM/database mapping layer. fileciteturn1file2L73-L89

The goal is not to create 20 endpoints quickly.

The goal is to build the system in dependency order:

```text
IDENTITY
   ↓
OWNERSHIP
   ↓
WALLET HIERARCHY
   ↓
TRANSACTION ENGINE
   ↓
FINANCIAL INTEGRITY
   ↓
ANALYTICS
   ↓
BUDGETS
   ↓
DATA IMPORT
   ↓
FINANCIAL EXTRAS
   ↓
AUTOMATION
   ↓
TESTING
   ↓
PRODUCTION HARDENING
```

That order prevents later features from being built on an unreliable financial core.
