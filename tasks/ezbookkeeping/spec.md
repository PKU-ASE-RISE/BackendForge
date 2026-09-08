# EZBookkeeping — Backend Implementation Spec

## Overview

EZBookkeeping is a **personal finance and expense tracking application** (inspired by [ezbookkeeping](https://github.com/mayswind/ezbookkeeping), 3K+ stars). Users manage accounts, categories, tags, and transactions. The system provides monthly statistics, category breakdowns, and CSV export.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID identifying the user

Rules:
- The `X-User-Id` header is required on **all** endpoints except `GET /health`.
- If the header is missing or empty on a protected endpoint, return `401 Unauthorized`.
- Trust the header value directly — it IS the user identifier. No database validation of users is needed. If a user with that UUID has never been seen before, treat them as a new user (their data starts empty).
- **Data scoping**: All data (accounts, categories, tags, transactions) is scoped to the authenticated user. A user can only see/modify their own data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (25+ endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Accounts — financial account management (2 paths, 5 methods)

Each account represents a financial account (wallet, bank account, credit card, etc.).

- `GET /accounts` — List all accounts for the current user (ordered by `displayOrder` ASC, then `createdAt` ASC)
- `POST /accounts` — Create an account (body: `name`, `type`, `currency`, `icon`, `displayOrder`)
- `GET /accounts/{id}` — Get a single account by ID
- `PUT /accounts/{id}` — Update an account (body: `name`, `type`, `currency`, `icon`, `displayOrder`)
- `DELETE /accounts/{id}` — Delete an account (fails if account has transactions)

### 2. Categories — transaction category management (2 paths, 5 methods)

Categories organize transactions. They support a two-level hierarchy (parent + child).

- `GET /categories` — List all categories for the current user (ordered by `displayOrder` ASC, then `createdAt` ASC)
- `POST /categories` — Create a category (body: `name`, `type`, `icon`, `color`, `parentId`, `displayOrder`)
- `GET /categories/{id}` — Get a single category by ID
- `PUT /categories/{id}` — Update a category (body: `name`, `icon`, `color`, `displayOrder`)
- `DELETE /categories/{id}` — Delete a category (fails if category has transactions or children)

### 3. Tags — transaction tag management (2 paths, 5 methods)

Tags provide cross-cutting labels for transactions.

- `GET /tags` — List all tags for the current user (ordered by `displayOrder` ASC, then `createdAt` ASC)
- `POST /tags` — Create a tag (body: `name`, `displayOrder`)
- `GET /tags/{id}` — Get a single tag by ID
- `PUT /tags/{id}` — Update a tag (body: `name`, `displayOrder`)
- `DELETE /tags/{id}` — Delete a tag (removes tag from all transactions, does not delete transactions)

### 4. Transactions — financial transaction management (2 paths, 5 methods)

Transactions are the core entity tracking money flow.

- `GET /transactions` — List transactions with filters (ordered by `date` DESC, then `createdAt` DESC). Supports query params: `accountId`, `categoryId`, `tagId`, `type`, `startDate`, `endDate`, `offset`, `limit`
- `POST /transactions` — Create a transaction (body: `type`, `amount`, `accountId`, `categoryId`, `tagIds`, `date`, `time`, `comment`, `destinationAccountId`)
- `GET /transactions/{id}` — Get a single transaction by ID
- `PUT /transactions/{id}` — Update a transaction (body: same as create)
- `DELETE /transactions/{id}` — Delete a transaction

### 5. Statistics — financial analytics (3 paths, 3 methods)

- `GET /statistics/monthly` — Monthly summary: total income, total expense, net balance for each month. Query params: `startMonth` (YYYY-MM), `endMonth` (YYYY-MM)
- `GET /statistics/category` — Category breakdown for a given month: sum of amounts per expense category. Query params: `month` (YYYY-MM), `type` (income/expense, default expense)
- `GET /statistics/trends` — Monthly trend data over a range. Query params: `startMonth` (YYYY-MM), `endMonth` (YYYY-MM)

### 6. Exchange Rates — currency conversion (1 path, 1 method)

- `GET /exchange-rates` — Get exchange rates. Query param: `base` (currency code, default USD). Returns hardcoded/mock rates.

### 7. Data Export — CSV export (1 path, 1 method)

- `GET /transactions/export` — Export transactions as CSV. Supports same filters as `GET /transactions`. Returns `text/csv` with columns: date, type, category, account, amount, comment, tags

### 8. Health — system status (1 path, 1 method)

- `GET /health` — Returns health status (no auth required)

---

**Totals: 14 paths, 26 endpoints across 8 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 14 paths / 26 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Account balance is computed**: An account's `balance` field is not stored directly — it is computed as: sum of income transactions to this account - sum of expense transactions from this account + sum of transfer-in amounts - sum of transfer-out amounts. When no transactions exist, balance is `0`.

2. **Transfer transactions are two-sided**: A transfer transaction debits the source account (`accountId`) and credits the destination account (`destinationAccountId`). The `amount` field represents the amount transferred. For statistics, transfers are excluded (they don't count as income or expense).

3. **Category hierarchy (max 2 levels)**: A category with `parentId = null` is a top-level (parent) category. A category with a valid `parentId` is a child (sub-category). A child category cannot itself be a parent (max depth = 2). A child category must have the same `type` as its parent — return `400 Bad Request` if they differ. Transactions must reference a leaf category (a category that has no children). If a category has children, it cannot be directly used in a transaction.

4. **Category type is immutable**: Once a category is created, its `type` cannot be changed via update.

5. **Transaction type must match category type**: An income transaction must use an income category. An expense transaction must use an expense category. A transfer transaction must use a transfer category.

6. **Transfer requires destinationAccountId**: If transaction type is `transfer`, `destinationAccountId` is required and must differ from `accountId`. For `income` and `expense` types, `destinationAccountId` must be null/absent.

7. **Monthly statistics**: `GET /statistics/monthly` aggregates transactions by month. For each month in the range, return `totalIncome`, `totalExpense`, and `net` (= totalIncome - totalExpense). Transfer transactions are excluded.

8. **Category breakdown**: `GET /statistics/category` returns the sum of transaction amounts grouped by category for the given month and type. Only returns categories that have transactions in that month.

9. **Display order**: Used for sorting in list endpoints. Lower values appear first. If two items have the same `displayOrder`, sort by `createdAt` ascending (older first).

10. **Account deletion blocked by transactions**: An account cannot be deleted if any transactions reference it (as `accountId` or `destinationAccountId`). Return `400 Bad Request`.

11. **Category deletion blocked by children or transactions**: A category cannot be deleted if it has child categories or if any transactions reference it. Return `400 Bad Request`.

12. **Tag deletion removes association**: Deleting a tag removes it from all transactions that use it, but does not delete those transactions.

13. **CSV export format**: Columns: `date,type,category,account,amount,comment,tags`. The `date` column uses ISO format (YYYY-MM-DD). The `tags` column is semicolon-separated tag names. Rows are ordered by date DESC.

14. **Currency on accounts**: Each account has a currency code (e.g., "USD", "EUR"). Transactions inherit currency from their account. Currency is informational — no automatic conversion is performed.

15. **Amount is always positive**: Transaction `amount` must be a positive number (> 0). The system interprets it based on transaction type (income = money in, expense = money out, transfer = money moved).

16. **Unique account names per user**: A user cannot have two accounts with the same name. Return `400 Bad Request` on duplicate.

17. **Unique category names per user within same type and parent**: A user cannot have two categories with the same name under the same parent and same type. Return `400 Bad Request` on duplicate.

18. **Unique tag names per user**: A user cannot have two tags with the same name. Return `400 Bad Request` on duplicate.

19. **Date format**: Transaction `date` field is `YYYY-MM-DD`. Transaction `time` field is `HH:MM:SS` (24-hour format). Both are stored and returned as strings.

20. **Pagination**: `GET /transactions` supports `offset` (default 0) and `limit` (default 50, max 200). Response includes `total` count, `offset`, and `limit` in a wrapping object.
