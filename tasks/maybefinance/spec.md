# Maybe Finance — Backend Implementation Spec

## Overview

A **personal finance dashboard** API (inspired by [Maybe](https://github.com/maybe-finance/maybe), 35K+ stars). Users manage financial accounts, track transactions, categorize spending, set budgets, and view insights like net worth and savings rate.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified multi-tenant):

- `X-User-Id`: UUID identifying the user

Rules:
- The `X-User-Id` header is required on **all endpoints**.
- If the header is missing or empty, return `401 Unauthorized`.
- Trust header values directly — no database lookup needed to validate the user.
- **Data scoping**: All data is scoped to the authenticated user. A user can only see/modify their own data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (36 endpoints across 9 endpoint groups). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Accounts — Financial account management (5 endpoints)

- `GET /accounts` — List all accounts for the current user
- `POST /accounts` — Create an account (201)
- `GET /accounts/{id}` — Get a single account (includes computed `holdings_value` for investment accounts)
- `PUT /accounts/{id}` — Update an account
- `DELETE /accounts/{id}` — Delete an account (cascades to transactions, holdings, syncs, budgets via category)

### 2. Transactions — Income/expense tracking (5 endpoints)

- `GET /transactions` — List transactions (supports filters: `account_id`, `category_id`, `tag_id`, `start_date`, `end_date`, `excluded`)
- `POST /transactions` — Create a transaction (201)
- `GET /transactions/{id}` — Get a single transaction
- `PUT /transactions/{id}` — Update a transaction
- `DELETE /transactions/{id}` — Delete a transaction

### 3. Categories — Hierarchical spending categories (5 endpoints)

- `GET /categories` — List all categories
- `POST /categories` — Create a category (201)
- `GET /categories/{id}` — Get a single category
- `PUT /categories/{id}` — Update a category
- `DELETE /categories/{id}` — Delete a category (sets transactions' category_id to null)

### 4. Tags — Flexible labels for transactions (5 endpoints)

- `GET /tags` — List all tags
- `POST /tags` — Create a tag (201)
- `GET /tags/{id}` — Get a single tag
- `PUT /tags/{id}` — Update a tag
- `DELETE /tags/{id}` — Delete a tag (removes from all transactions)

### 5. Holdings — Investment positions (5 endpoints)

- `GET /accounts/{id}/holdings` — List holdings for an investment account
- `POST /accounts/{id}/holdings` — Create a holding (201)
- `GET /accounts/{id}/holdings/{holding_id}` — Get a single holding
- `PUT /accounts/{id}/holdings/{holding_id}` — Update a holding
- `DELETE /accounts/{id}/holdings/{holding_id}` — Delete a holding

### 6. Net Worth — Financial summary (1 endpoint)

- `GET /net-worth` — Compute current net worth breakdown

### 7. Account Syncs — Simulated sync events (2 endpoints)

- `POST /accounts/{id}/syncs` — Create a sync (updates balance, adds transactions) (201)
- `GET /accounts/{id}/syncs` — List sync history for an account

### 8. Budgets — Monthly budget tracking (5 endpoints)

- `GET /budgets` — List budgets (query: `month`, `year`)
- `POST /budgets` — Create a budget (201)
- `GET /budgets/{id}` — Get a single budget (includes computed `actual` and `remaining`)
- `PUT /budgets/{id}` — Update a budget
- `DELETE /budgets/{id}` — Delete a budget

### 9. Insights — Spending analytics (3 endpoints)

- `GET /insights/spending-by-category` — Spending breakdown by category
- `GET /insights/income-vs-expenses` — Income vs expenses summary
- `GET /insights/savings-rate` — Savings rate calculation

---

**Totals: 36 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 36 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

### Currency & Amounts

1. **All monetary amounts are in cents** (integer). For example, $150.00 is stored as `15000`.
2. **Transaction amount is always a positive integer.** The category type (income/expense) determines direction.
3. **Single currency** — no conversion needed. The `currency` field on accounts is informational only (default "USD").

### Account Types & Net Worth

4. **Account types**: `depository`, `investment`, `crypto`, `property`, `vehicle`, `loan`, `credit_card`, `other`.
5. **Net worth calculation**:
   - Assets = sum of balances for accounts with types: depository, investment, crypto, property, vehicle, other (only those with positive balance)
   - Assets also includes sum of all holdings' `current_value` for investment accounts
   - Liabilities = absolute value of balances for accounts with types: loan, credit_card
   - Net worth = assets - liabilities
6. **Investment accounts** contribute: account.balance (cash) + sum(holdings.current_value) to assets.
7. **Loan/credit_card** balances are stored as **negative integers** (e.g., -50000 = you owe $500).

### Holdings

8. **Holdings are only valid for investment accounts.** Creating a holding for a non-investment account returns `400 Bad Request`.
9. **Holding fields**: `symbol` (e.g., "AAPL"), `shares` (decimal as float, e.g., 10.5), `cost_basis` (cents), `current_value` (cents).

### Transactions & Categories

10. **Transaction amount is always positive.** Whether it's income or expense is determined by the linked category's type.
11. **Excluded transactions** (`excluded: true`) are NOT counted in budgets, insights, or net worth calculations.
12. **Uncategorized transactions** (category_id is null) are ignored in budget calculations and spending-by-category insights, but ARE counted in income-vs-expenses only if they have a category.
13. **Tags**: A transaction can have multiple tags (many-to-many). Tags are passed as an array of tag IDs.

### Category Hierarchy

14. **Parent categories**: A category can have a `parent_id` pointing to another category. Max one level of nesting (a child cannot itself be a parent).
15. **Rollup**: In spending-by-category insights, spending in child categories rolls up to the parent. The parent shows total = own transactions + children's transactions.
16. **Deleting a parent category**: Sets children's `parent_id` to null (they become top-level).
17. **Cannot set parent_id to a category that already has a parent** (no grandchildren). Return `400`.
18. **Cannot set a category's parent_id to itself.** Return `400`.

### Budgets

19. **Budget uniqueness**: Only one budget per (user, category_id, month, year). Duplicate returns `400`.
20. **Budget `actual`**: Sum of transaction amounts where category matches (including child categories that roll up to this category), transaction is in the budget's month/year, AND transaction is not excluded.
21. **Budget `remaining`**: `amount - actual`. Can be negative (overspent).
22. **Budget month/year filter**: GET /budgets supports `month` and `year` query params. Both are required when filtering — if only one is provided, return `400`.

### Account Syncs

23. **Sync simulation**: POST /accounts/{id}/syncs accepts `balance` (new balance) and `transactions` (array of transaction objects to create). It:
    - Records the old balance (`balance_before`)
    - Updates the account balance to the new value (`balance_after`)
    - Creates the provided transactions (linked to this account)
    - Returns the sync record with `transactions_created` count
24. **Sync transactions**: Each transaction in the sync body needs at minimum: `date`, `amount`, `name`. Optional: `category_id`.

### Insights

25. **Spending by category** (GET /insights/spending-by-category?month=X&year=Y):
    - Returns array of { category_id, category_name, amount, previous_amount, change_percent }
    - `amount` = sum of transaction amounts for expense categories in the given month
    - `previous_amount` = same calculation for the previous month
    - `change_percent` = ((amount - previous_amount) / previous_amount) * 100, or null if previous_amount is 0
    - Only includes expense categories with at least one transaction in either month
    - Child category spending rolls up to parent (reported under parent)
    - Excluded transactions are excluded
    - month and year are required. Missing either returns `400`.

26. **Income vs Expenses** (GET /insights/income-vs-expenses?month=X&year=Y):
    - Returns { income, expenses, net }
    - income = sum of amounts for transactions with income-type categories in the given month
    - expenses = sum of amounts for transactions with expense-type categories in the given month
    - net = income - expenses
    - Excluded transactions are excluded
    - month and year are required. Missing either returns `400`.

27. **Savings rate** (GET /insights/savings-rate?month=X&year=Y):
    - Returns { savings_rate, income, expenses }
    - savings_rate = ((income - expenses) / income) * 100, rounded to 2 decimal places
    - If income is 0, savings_rate = 0.0
    - Excluded transactions are excluded
    - month and year are required. Missing either returns `400`.

### Data Isolation & Ownership

28. **All data is scoped to the user.** Accessing another user's resource returns `404 Not Found`.
29. **Cross-reference validation**: A transaction's `account_id` must belong to the same user. A transaction's `category_id` (if provided) must belong to the same user. A transaction's tag IDs must all belong to the same user. If any are invalid, return `400`.
30. **Deleting an account** cascades: removes all transactions for that account, all holdings, and all syncs.
31. **Deleting a category** sets `category_id` to null on all transactions that used it. Also deletes any budgets for that category.
32. **Deleting a tag** removes it from all transactions (many-to-many cleanup).
