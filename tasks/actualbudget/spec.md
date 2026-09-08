# Actual Budget — Backend Implementation Spec

## Overview

Actual Budget is a **personal envelope budgeting application** (inspired by [Actual Budget](https://github.com/actualbudget/actual), 16K+ stars). Users create accounts, track transactions, assign monthly budgets to categories, set up auto-categorization rules, and schedule recurring transactions. It supports multi-user isolation via a simple header-based auth.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID string identifying the user

Rules:
- The `X-User-Id` header is required on **all** endpoints.
- If the header is missing or empty, return `401 Unauthorized`.
- Trust header values directly — do not validate against a user table. The UUID IS the user identity.
- **Data scoping**: All data (accounts, categories, transactions, etc.) is scoped to the authenticated user. A user can only see/modify their own data.
- There is no admin concept — every user has equal access to their own budget.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (30+ paths, 40+ endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Accounts — bank/credit account tracking (2 paths, 5 methods)

Accounts represent real-world financial accounts (checking, savings, credit cards, etc.). Balance is computed from transactions.

- `GET /accounts` — List all accounts for the current user
- `POST /accounts` — Create an account (body: `name`, `type`, `offBudget`)
- `GET /accounts/{id}` — Get a single account with computed balance
- `PUT /accounts/{id}` — Update an account (body: `name`, `type`, `offBudget`, `closed`)
- `DELETE /accounts/{id}` — Delete an account (also deletes all its transactions)

### 2. Category Groups — organize categories into groups (2 paths, 5 methods)

- `GET /category-groups` — List all category groups (with nested categories)
- `POST /category-groups` — Create a category group
- `GET /category-groups/{id}` — Get a single category group with its categories
- `PUT /category-groups/{id}` — Update a category group
- `DELETE /category-groups/{id}` — Delete a category group (also deletes its categories)

### 3. Categories — budget categories (2 paths, 5 methods)

- `GET /categories` — List all categories
- `POST /categories` — Create a category (body: `name`, `groupId`, `isIncome`, `sortOrder`)
- `GET /categories/{id}` — Get a single category
- `PUT /categories/{id}` — Update a category
- `DELETE /categories/{id}` — Delete a category

### 4. Payees — transaction counterparties (2 paths, 5 methods)

- `GET /payees` — List all payees
- `POST /payees` — Create a payee (body: `name`, `categoryId`)
- `GET /payees/{id}` — Get a single payee
- `PUT /payees/{id}` — Update a payee
- `DELETE /payees/{id}` — Delete a payee

### 5. Transactions — the core ledger (2 paths, 5 methods)

- `GET /transactions` — List transactions (supports filtering by `accountId`, `categoryId`, `startDate`, `endDate`, `limit`, `offset`)
- `POST /transactions` — Create a transaction (auto-applies rules)
- `GET /transactions/{id}` — Get a single transaction
- `PUT /transactions/{id}` — Update a transaction
- `DELETE /transactions/{id}` — Delete a transaction

### 6. Budgets — monthly envelope amounts (2 paths, 3 methods)

- `GET /budgets/{month}` — Get all budget amounts for a month (format: `YYYY-MM`)
- `PUT /budgets/{month}/categories/{categoryId}` — Set budget amount for a category in a month
- `GET /budgets/{month}/categories/{categoryId}` — Get budget detail for a specific category in a month (budgeted, spent, available)

### 7. Rules — auto-categorization (2 paths, 5 methods)

- `GET /rules` — List all rules
- `POST /rules` — Create a rule
- `GET /rules/{id}` — Get a single rule
- `PUT /rules/{id}` — Update a rule
- `DELETE /rules/{id}` — Delete a rule

### 8. Schedules — recurring transactions (3 paths, 6 methods)

- `GET /schedules` — List all schedules
- `POST /schedules` — Create a schedule
- `GET /schedules/{id}` — Get a single schedule
- `PUT /schedules/{id}` — Update a schedule
- `DELETE /schedules/{id}` — Delete a schedule
- `POST /schedules/{id}/post-transaction` — Manually trigger a scheduled transaction (creates the transaction and advances `nextDate`)

### 9. Reports — aggregated financial data (3 paths, 3 methods)

- `GET /reports/spending-by-category` — Category-level spending for a date range
- `GET /reports/net-worth` — Net worth over time (monthly data points)
- `GET /reports/income-vs-expenses` — Monthly income vs expenses summary

---

**Totals: 22 paths, 42 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 22 paths / 42 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Account balance is computed**: An account's `balance` field is the sum of all transaction amounts for that account. It is NOT stored as a column — it is derived from transactions on every read.

2. **Amounts are integers (cents)**: All monetary amounts are stored as integers representing cents (e.g., $10.50 = 1050). Positive amounts are income/credits, negative amounts are expenses/debits.

3. **Transfers**: When creating a transaction with `transferAccountId` set, the system MUST automatically create a mirror transaction in the target account. The mirror transaction has the negated amount, references the original account as its `transferAccountId`, and the same date/cleared/payee. Both transactions reference each other. When deleting a transfer transaction, the mirror transaction is also deleted.

4. **Envelope budgeting**: Each month, you assign money to categories via `PUT /budgets/{month}/categories/{categoryId}`. The `available` amount for a category in a month is: `budgeted - spent`, where `spent` is the absolute value of the sum of negative transactions in that category during that month.

5. **Rules auto-apply on transaction creation**: When creating a transaction via `POST /transactions`, the system checks all rules in order. If a rule's conditions match, its actions are applied. Rules do NOT apply on update — only on creation.

6. **Rule conditions**: Each rule has an array of `conditions`. Each condition has `field` (payee/amount/notes), `op` (is/contains/gt/lt), and `value`. ALL conditions must match for the rule to fire (AND logic).

7. **Rule actions**: Each rule has an array of `actions`. Each action has `field` (category/payee) and `value` (the ID to set). Actions are applied in order.

8. **Rule condition matching**:
   - `field=payee, op=is`: transaction payee name (looked up from payeeId) equals value (case-insensitive)
   - `field=payee, op=contains`: transaction payee name contains value (case-insensitive)
   - `field=amount, op=gt`: transaction amount > value (value is integer cents)
   - `field=amount, op=lt`: transaction amount < value (value is integer cents)
   - `field=notes, op=is`: transaction notes equals value (case-insensitive)
   - `field=notes, op=contains`: transaction notes contains value (case-insensitive)

9. **Payee default category**: If a payee has a `categoryId` set and a transaction is created with that payee but NO explicit category, the payee's default category is used. Rules take precedence over payee defaults.

10. **Schedule posting**: `POST /schedules/{id}/post-transaction` creates a transaction from the schedule's template (amount, accountId, categoryId, payeeId) with the schedule's `nextDate` as the transaction date. Then it advances `nextDate` based on `frequency`: weekly (+7 days), monthly (+1 month), yearly (+1 year).

11. **Schedule nextDate advancement**: When advancing monthly, if the original day doesn't exist in the target month (e.g., Jan 31 → Feb), use the last day of the target month.

12. **Cascade delete — accounts**: Deleting an account deletes all transactions in that account (including mirror transactions of transfers).

13. **Cascade delete — category groups**: Deleting a category group deletes all categories in that group.

14. **Category group nesting**: When listing category groups, each group includes a `categories` array with all categories in that group.

15. **Net worth report**: Returns monthly data points. Each point's value is the sum of all account balances (sum of all transactions up to the end of that month). Query params: `startMonth` and `endMonth` (format: YYYY-MM).

16. **Income vs expenses report**: Income = sum of positive amounts in income categories. Expenses = absolute value of sum of negative amounts in non-income categories. Query params: `startMonth` and `endMonth`.

17. **Spending by category report**: For each category, sum of negative transaction amounts in the date range. Query params: `startDate` and `endDate` (format: YYYY-MM-DD).

18. **Transaction filtering**: `GET /transactions` supports query params: `accountId`, `categoryId`, `payeeId`, `startDate`, `endDate`, `limit` (default 50, max 200), `offset` (default 0).

19. **Unique names per user**: Account names, category names (within the same group), category group names, and payee names must be unique per user. Return 400 on duplicate.

20. **Account types**: Valid types are: `checking`, `savings`, `credit_card`, `investment`, `cash`. Invalid type returns 400.
