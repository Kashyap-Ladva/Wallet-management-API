# Wallet Management API — Next-Level Development Plan

## 1. Project Objective

The current project has moved beyond the original CRUD wallet API.

The target system is a **multi-user personal wallet and expense-management backend** built with:

- Python
- FastAPI
- Pydantic
- SQLAlchemy ORM
- PostgreSQL
- REST APIs
- Authentication/authorization
- Excel data import
- File/proof handling
- Financial analytics
- Scheduled summaries/reminders

The database schema, SQLAlchemy models, and PostgreSQL database layer are already prepared. The remaining work is application behavior, APIs, business rules, analytics, ingestion, scheduling, testing, and production hardening.

## 2. Current Data Model

The current model establishes:

```text
User
  │
  │ 1 : 1
  ▼
Super Wallet
  │
  ├──────── 1 : many ───────► Mini Wallet
  │                              │
  │                              └── 1 : many ──► Transactions
  │
  └──────── 1 : many ───────► Transactions
```

The supplied SQLAlchemy model enforces one super wallet per user through a unique `user_id`, connects mini wallets to the super wallet, and connects transactions to both wallet levels. The super-wallet balance is derived from mini-wallet balances, while a mini-wallet balance is derived from its transactions. fileciteturn1file0L1-L1

The current transaction schema already supports:

- income / expense
- amount
- category
- description
- date
- mode of payment
- proof

and validates positive amounts and the two transaction types at the Pydantic level. fileciteturn1file1L1-L1

## 3. Functional Scope

The final system must support:

1. User registration/login/password authentication.
2. Exactly one super wallet per user.
3. Multiple mini wallets under a super wallet.
4. Mini wallets representing modes such as card, cash, UPI, bank, etc.
5. Transaction creation and update.
6. Income and expense transactions.
7. Correct mini-wallet and cumulative super-wallet balances.
8. Persistent transaction dates.
9. Transaction history.
10. Daily, monthly and yearly summaries.
11. Category-wise comparison.
12. Mini-wallet comparison.
13. Bar-chart/pie-chart data APIs.
14. Daily/monthly spending targets.
15. Limit-crossing detection.
16. Excel upload and database import.
17. Payment proof as image or text.
18. Savings/investment records.
19. Daily end-of-day summary.
20. Start-of-month bill/fixed-payment reminders.
21. Debt/credit/lending tracking.
22. Testing, validation, authorization and production hardening.

---

# 4. Five-Phase Development Strategy

The project should be built in dependency order.

```text
PHASE 1
Identity + Wallet Foundation
        ↓
PHASE 2
Transaction Engine + Financial Integrity
        ↓
PHASE 3
Analytics + Budgets + Dashboard Data
        ↓
PHASE 4
Import + Proof + Savings + Debt + Scheduled Features
        ↓
PHASE 5
Production Hardening + Testing + Optimization
```

The important principle is:

> Do not implement analytics or automation before the transaction engine is reliable.

---

# PHASE 1 — Identity, Authentication & Wallet Foundation

## Goal

Create the secure user boundary and complete the core wallet hierarchy.

## Covers

- User registration
- Password handling
- Login
- Authentication
- Authorization
- User profile
- One super wallet per user
- Mini-wallet CRUD
- Wallet ownership checks
- Basic wallet retrieval

## Functional requirements

### 1. Authentication

Flow:

```text
Register
   ↓
Validate user data
   ↓
Hash password
   ↓
Store user
   ↓
Login
   ↓
Verify password
   ↓
Issue access token
   ↓
Authenticated API requests
```

Important rule:

```text
Never store plaintext passwords.
```

Use a password hashing library and JWT/OAuth2-style bearer authentication.

### 2. Authorization

Every protected request must identify the current user.

```text
Request
   ↓
Bearer token
   ↓
Authenticate user
   ↓
Get current_user
   ↓
Check resource ownership
   ↓
Allow / reject
```

A user must never be able to access another user's wallet or transactions by changing an ID in the URL.

### 3. Super wallet

Rules:

```text
One User
   ↓
Exactly One Super Wallet
```

Creating a second super wallet must return a controlled error.

### 4. Mini wallets

Example:

```text
Super Wallet
│
├── Cash
├── HDFC Credit Card
├── UPI
├── Bank Account
└── Other
```

Mini wallets can be created, viewed, updated and deleted subject to transaction/ownership rules.

## Phase 1 endpoints

```text
POST   /auth/register
POST   /auth/login
GET    /users/me
PUT    /users/me

POST   /super-wallet
GET    /super-wallet
PUT    /super-wallet

POST   /super-wallet/mini-wallets
GET    /super-wallet/mini-wallets
GET    /mini-wallets/{mini_wallet_id}
PUT    /mini-wallets/{mini_wallet_id}
DELETE /mini-wallets/{mini_wallet_id}
```

## Phase 1 exit criteria

- User can register.
- User can login.
- Protected endpoints reject unauthenticated requests.
- User can access only their own resources.
- User can create only one super wallet.
- User can create multiple mini wallets.
- Swagger authentication works.

---

# PHASE 2 — Transaction Engine & Financial Integrity

## Goal

Build the core financial engine.

This is the most important phase because almost every later feature depends on correct transaction data.

## Covers

- Add income
- Add expense
- Update transaction
- Delete transaction
- Transaction history
- Date persistence
- Mini-wallet balance
- Super-wallet cumulative balance
- Category
- Mode of payment
- Payment proof metadata
- Financial consistency

The current model already represents transactions under both mini and super wallets and supports date, category, payment mode and proof fields. fileciteturn1file0L96-L135

## Core transaction flow

```text
Authenticated User
        ↓
Select Mini Wallet
        ↓
Create Transaction
        ↓
Validate ownership
        ↓
Validate amount/type/date
        ↓
Create transaction
        ↓
Commit PostgreSQL transaction
        ↓
Mini-wallet balance changes
        ↓
Super-wallet cumulative balance changes
        ↓
Return transaction
```

## Balance rules

For income:

```text
Mini Balance = Mini Balance + Amount
```

For expense:

```text
Mini Balance = Mini Balance - Amount
```

Super wallet:

```text
Super Balance
    =
sum(all mini-wallet balances)
```

The current SQLAlchemy model already derives the super-wallet total from mini-wallet balances and mini-wallet balance from transaction types. fileciteturn1file0L58-L60 fileciteturn1file0L83-L94

## Critical update/delete rule

Do not simply overwrite a transaction.

Example:

```text
Old:
Expense ₹2,000

New:
Expense ₹3,000
```

The system must apply the difference:

```text
Old effect = -₹2,000
New effect = -₹3,000

Balance difference = -₹1,000
```

If the transaction changes:

```text
income → expense
```

or:

```text
expense → income
```

the old financial effect must be reversed before the new effect is applied.

## Transaction history

Support:

```text
GET /transactions
GET /mini-wallets/{id}/transactions
GET /super-wallet/transactions
```

Filters:

```text
date_from
date_to
type
category
mini_wallet_id
modeofpayment
```

## Payment proof

Recommended architecture:

```text
Image/Text Proof
       ↓
Upload/validation layer
       ↓
Object/file storage
       ↓
Store file key/URL in database
```

Do not store large image binaries directly inside the transaction table unless there is a specific requirement for database BLOB storage.

The existing transaction model has a `proof` string field, so it can hold a proof reference or textual proof value. fileciteturn1file0L120-L125

## Phase 2 endpoints

```text
POST   /mini-wallets/{mini_wallet_id}/transactions
GET    /mini-wallets/{mini_wallet_id}/transactions
GET    /transactions/{transaction_id}
PUT    /transactions/{transaction_id}
DELETE /transactions/{transaction_id}

GET    /super-wallet/balance
GET    /mini-wallets/{mini_wallet_id}/balance

POST   /transactions/{transaction_id}/proof
GET    /transactions/{transaction_id}/proof
```

## Phase 2 exit criteria

- Income works.
- Expense works.
- Update works without corrupting balance.
- Delete works without corrupting balance.
- Dates remain unchanged/persistent.
- Mini-wallet balances are correct.
- Super-wallet balance is correct.
- Transaction history works.
- Unauthorized cross-user access is impossible.

---

# PHASE 3 — Analytics, Comparisons, Budgets & Dashboard Data

## Goal

Turn raw transactions into useful financial information.

## Covers

- Daily summary
- Monthly summary
- Yearly summary
- Mini-wallet comparison
- Category comparison
- Category pie-chart data
- Daily/monthly bar-chart data
- Expense targets
- Limit crossing
- Dashboard API

## Analytics principle

Do not calculate analytics in the router.

Use:

```text
Router
   ↓
Analytics Service
   ↓
SQL aggregation queries
   ↓
Response schema
```

## 1. Daily summary

Example:

```text
Date: 2026-10-02

Income:  ₹2,000
Expense: ₹850
Net:     ₹1,150
```

## 2. Monthly summary

Return:

```text
total_income
total_expense
net
transaction_count
category_breakdown
mini_wallet_breakdown
```

## 3. Yearly summary

Return monthly aggregates:

```text
Jan
Feb
Mar
...
Dec
```

This becomes the data source for yearly bar charts.

## 4. Mini-wallet comparison

Example:

```text
Cash          ₹8,000 expense
Credit Card   ₹15,000 expense
UPI           ₹6,500 expense
Bank          ₹4,000 expense
```

The API returns comparable numeric data. The frontend/client is responsible for rendering the chart.

## 5. Category comparison

Example:

```text
Food       ₹8,000
Travel     ₹5,000
Rent       ₹12,000
Shopping   ₹3,000
```

## 6. Pie-chart API

```text
GET /analytics/expenses/categories
```

Response should be chart-friendly:

```json
{
  "labels": ["Food", "Travel", "Rent"],
  "values": [8000, 5000, 12000]
}
```

## 7. Bar-chart API

```text
GET /analytics/expenses/monthly
```

Example:

```json
{
  "labels": ["Jan", "Feb", "Mar"],
  "values": [12000, 14000, 11000]
}
```

## 8. Spending targets

Support:

```text
daily target
monthly target
```

Flow:

```text
Set target
   ↓
Store target
   ↓
Calculate current spending
   ↓
Compare spending with target
   ↓
Return status
```

Example:

```text
Monthly target = ₹20,000
Current expense = ₹21,500
Exceeded = ₹1,500
```

The API should return the facts:

```text
target
spent
remaining
exceeded
percentage_used
```

## Phase 3 endpoints

```text
GET  /analytics/daily
GET  /analytics/monthly
GET  /analytics/yearly

GET  /analytics/mini-wallets
GET  /analytics/categories
GET  /analytics/expenses/pie
GET  /analytics/expenses/bar

POST /budgets
GET  /budgets
PUT  /budgets/{budget_id}
DELETE /budgets/{budget_id}

GET  /budgets/{budget_id}/status
```

## Phase 3 exit criteria

- Daily/monthly/yearly data is correct.
- Category totals are correct.
- Mini-wallet comparisons are correct.
- Chart endpoints return clean frontend-ready data.
- Daily/monthly targets can be created and evaluated.
- Target crossing is detected reliably.

---

# PHASE 4 — Data Import, Financial Extras & Automation

## Goal

Add the advanced user-facing capabilities.

## Covers

- Excel upload
- Data validation/import
- Savings
- Investments
- Debt/credit
- Lending/borrowing records
- Fixed bills
- Monthly reminders
- Daily summaries

## 1. Excel import

Flow:

```text
Upload Excel
      ↓
Validate extension
      ↓
Read workbook
      ↓
Validate columns
      ↓
Normalize values
      ↓
Validate dates/amounts/types
      ↓
Validate wallet ownership
      ↓
Preview / import
      ↓
Database transaction
      ↓
Create transactions
      ↓
Update financial state
```

Recommended behavior:

```text
Upload
  ↓
Preview errors
  ↓
User confirms
  ↓
Import
```

Do not immediately insert an unvalidated spreadsheet into PostgreSQL.

## 2. Savings

Savings should be represented independently from normal spending transactions.

Possible concepts:

```text
Savings Goal
Savings Contribution
Current Saved Amount
Target Amount
Progress
```

## 3. Investments

Track:

```text
investment name
amount
date
type
notes
```

Keep investment tracking separate from ordinary expense categories unless the final product explicitly defines investment purchases as expenses.

## 4. Debt / credit

Support both:

```text
Money I lent
Money I borrowed
```

Example:

```text
Person
Amount
Direction
Date
Due date
Status
Notes
```

Statuses:

```text
pending
partially_paid
settled
```

## 5. Fixed payments

Create a recurring payment/reminder record:

```text
Name
Amount
Due day
Frequency
Category
Active
```

Examples:

```text
Rent
Internet
Electricity
Subscription
EMI
Insurance
```

## 6. Daily summary

At the end of the day:

```text
Fetch today's transactions
       ↓
Calculate income
       ↓
Calculate expense
       ↓
Category breakdown
       ↓
Mini-wallet breakdown
       ↓
Budget status
       ↓
Generate summary
       ↓
Deliver notification/message
```

## 7. Monthly reminder

At the beginning of the month:

```text
Find active recurring payments
       ↓
Find upcoming due dates
       ↓
Generate reminders
       ↓
Deliver notification
```

For a simple first implementation, an application scheduler can run jobs. For a multi-instance production deployment, use a durable background-job system/queue rather than relying only on an in-process scheduler.

## Phase 4 endpoints

```text
POST /imports/excel
POST /imports/excel/preview
POST /imports/excel/confirm

POST /savings
GET  /savings
PUT  /savings/{id}
DELETE /savings/{id}

POST /investments
GET  /investments
PUT  /investments/{id}
DELETE /investments/{id}

POST /debts
GET  /debts
PUT  /debts/{id}
DELETE /debts/{id}

POST /recurring-payments
GET  /recurring-payments
PUT  /recurring-payments/{id}
DELETE /recurring-payments/{id}
```

---

# PHASE 5 — Production Hardening, Testing & Optimization

## Goal

Make the system reliable enough to behave like a real backend application.

## Covers

- Automated tests
- Integration tests
- Database transaction safety
- Authorization testing
- Input validation
- Pagination
- Filtering
- Indexing
- Logging
- Configuration management
- File validation
- Rate limiting where appropriate
- API documentation
- Docker
- Deployment readiness
- Monitoring/health checks

## 1. Testing layers

```text
Unit Tests
    ↓
Service Tests
    ↓
API Tests
    ↓
Database Integration Tests
    ↓
End-to-End Critical Flows
```

Critical flow:

```text
Register
  ↓
Login
  ↓
Create Super Wallet
  ↓
Create Mini Wallet
  ↓
Add Income
  ↓
Add Expense
  ↓
Update Expense
  ↓
Check Balance
  ↓
Check Analytics
  ↓
Set Budget
  ↓
Cross Budget
```

## 2. Database integrity

Every financial mutation should be atomic.

Example:

```text
Create Transaction
+
Update Financial State
+
Related database changes
```

must succeed together or roll back together.

## 3. Pagination

Transaction history can become large.

Use:

```text
limit
offset
```

or cursor-based pagination for larger datasets.

## 4. Indexing

Review indexes for frequently queried fields:

```text
user_id
super_wallet_id
mini_wallet_id
date_created
category
type
```

Only add indexes based on actual query patterns.

## 5. Security checklist

```text
Password hashing
JWT/access-token validation
Resource ownership checks
Input validation
File type validation
File size limits
Safe filenames/storage keys
Secret management
CORS configuration
Rate limiting where needed
```

## 6. Observability

Add:

```text
structured logging
request IDs
error logging
health endpoint
database health check
```

## Phase 5 exit criteria

- Critical APIs have automated tests.
- Authentication and ownership tests pass.
- Financial operations are atomic.
- Large transaction lists are paginated.
- Logs and health checks work.
- Configuration/secrets are environment-based.
- Application can be containerized and deployed.

---

# 5. Final Architecture

Target architecture:

```text
                         CLIENT
                           │
                           ▼
                    FastAPI Application
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
          Auth Layer               API Routers
                                      │
        ┌───────────────┬─────────────┼───────────────┐
        ▼               ▼             ▼               ▼
     Wallet          Transaction   Analytics       Imports
     Router           Router       Router          Router
        │               │             │               │
        └───────────────┴──────┬──────┴───────────────┘
                               ▼
                         Service Layer
                               │
        ┌──────────────┬───────┼───────────┬───────────┐
        ▼              ▼       ▼           ▼           ▼
     Wallet        Transaction Analytics  Import    Scheduler
     Service       Service      Service   Service     Jobs
        │              │          │         │
        └──────────────┴──────────┴─────────┘
                               │
                               ▼
                        SQLAlchemy ORM
                               │
                               ▼
                         PostgreSQL
```

External/supporting systems:

```text
Image/File Storage
       ▲
       │
   Proof Service

Scheduler / Queue
       │
       ├── Daily Summary
       └── Monthly Reminders
```

---

# 6. Final Functional Flow

```text
USER
 │
 ├── Register / Login
 │        ↓
 │     Auth Token
 │        ↓
 │
 └── Super Wallet
          │
          ├── Mini Wallet: Cash
          │       └── Transactions
          │
          ├── Mini Wallet: Card
          │       └── Transactions
          │
          ├── Mini Wallet: UPI
          │       └── Transactions
          │
          └── Mini Wallet: Bank
                  └── Transactions
                          │
                          ▼
                    Financial Engine
                          │
             ┌────────────┼─────────────┐
             ▼            ▼             ▼
          Balances     Analytics      Budgets
             │            │             │
             ▼            ▼             ▼
         Dashboard     Charts        Alerts
                          │
          ┌───────────────┼────────────────┐
          ▼               ▼                ▼
       Savings          Debt           Investments
                          │
                          ▼
                     Automation
                          │
                 ┌────────┴────────┐
                 ▼                 ▼
           Daily Summary     Monthly Reminder
```

---

# 7. Requirement-to-Phase Mapping

| Requirement | Phase |
|---|---|
| Login/password/auth | 1 |
| One super wallet | 1 |
| User → super wallet 1:1 | 1 |
| Super wallet → mini wallets | 1 |
| Mini wallet → transactions | 2 |
| Update transactions | 2 |
| Transaction history | 2 |
| Income/expense | 2 |
| Mini/super balance | 2 |
| Persistent dates | 2 |
| Payment proof | 2 |
| Mini-wallet comparison | 3 |
| Daily/monthly/yearly summaries | 3 |
| Category comparison | 3 |
| Expense targets | 3 |
| Limit crossing | 3 |
| Pie chart data | 3 |
| Bar chart data | 3 |
| Excel import | 4 |
| Savings | 4 |
| Investments | 4 |
| Debt/credit | 4 |
| Daily summary | 4 |
| Monthly bill reminders | 4 |
| Testing | 5 |
| Security hardening | 5 |
| Pagination/indexing/optimization | 5 |
| Docker/deployment readiness | 5 |

---

# 8. Development Rule

Implement in this exact order:

```text
1. Authentication
2. User ownership
3. Super wallet
4. Mini wallets
5. Transaction engine
6. Balance correctness
7. Transaction history
8. Analytics
9. Budgets
10. Chart APIs
11. Excel import
12. Savings/investments
13. Debt/credit
14. Scheduled summaries/reminders
15. Testing
16. Security hardening
17. Performance optimization
18. Deployment
```

Do not jump to charts, reminders, or Excel import before the transaction engine is correct.

---

# 9. Definition of Done

The project is complete when:

- [ ] User registration works.
- [ ] Passwords are securely hashed.
- [ ] Login and token authentication work.
- [ ] Protected endpoints identify the current user.
- [ ] Cross-user resource access is blocked.
- [ ] One super wallet per user is enforced.
- [ ] Multiple mini wallets work.
- [ ] Income transactions work.
- [ ] Expense transactions work.
- [ ] Transaction update/delete correctly reverses old financial effects.
- [ ] Mini-wallet balances are correct.
- [ ] Super-wallet balance is correct.
- [ ] Transaction dates persist correctly.
- [ ] Transaction history supports filtering/pagination.
- [ ] Payment proof can be stored/retrieved safely.
- [ ] Daily/monthly/yearly analytics work.
- [ ] Mini-wallet comparison works.
- [ ] Category comparison works.
- [ ] Pie/bar chart data APIs work.
- [ ] Daily/monthly spending targets work.
- [ ] Target crossing is detected.
- [ ] Excel import validates and imports data safely.
- [ ] Savings tracking works.
- [ ] Investment tracking works.
- [ ] Debt/credit tracking works.
- [ ] Recurring payments can be stored.
- [ ] Daily summaries are generated.
- [ ] Monthly reminders are generated.
- [ ] Automated tests cover critical financial flows.
- [ ] Database operations are atomic.
- [ ] Pagination and appropriate indexes are implemented.
- [ ] Logging and health checks work.
- [ ] Secrets are not hardcoded.
- [ ] Docker/deployment configuration is ready.

---

# 10. Immediate Next Step

Start with **Phase 1 only**.

Before writing routes, verify the authentication data model.

The currently supplied `User` model contains:

```text
id
name
phone
email
currency
date_created
```

but no password-hash/authentication field is shown. fileciteturn0file3L4-L9

Therefore the first implementation task is:

```text
User authentication fields
        ↓
Password hashing
        ↓
Register endpoint
        ↓
Login endpoint
        ↓
JWT/access-token dependency
        ↓
Current-user dependency
        ↓
Super-wallet ownership
```

Do not start Phase 2 until Phase 1 authentication and ownership checks are working.
