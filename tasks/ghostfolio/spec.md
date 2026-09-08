# Ghostfolio — Backend Implementation Spec

## Overview

Ghostfolio is an **open-source wealth management and portfolio tracking application** (based on [Ghostfolio](https://github.com/ghostfolio/ghostfolio), 8.3K stars). Users track their investment accounts, record buy/sell/dividend activities, and view computed portfolio performance including holdings, gain/loss, and allocation breakdowns.

The application supports multi-user portfolios with real-time portfolio valuation based on market data. For this benchmark, market data is mocked with fixed prices for a set of known symbols.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID string identifying the user

Rules:
- The `X-User-Id` header is required on all endpoints **except** `/api/health`.
- If the header is missing on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — the UUID IS the user identifier. If a user with that ID doesn't exist, **auto-create** the user with that ID and a default `baseCurrency` of `USD`.
- **Data scoping**: All accounts, activities, tags, holdings, and portfolio data are scoped to the authenticated user. A user can only see/modify their own data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (25+ paths, 35+ endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Accounts — Investment account management (2 paths, 5 methods)

Accounts represent brokerage or bank accounts where assets are held.

- `GET /api/accounts` — List all accounts for the current user
- `POST /api/accounts` — Create an account (body: `name`, `accountType`, `currency`, `balance`)
- `GET /api/accounts/{id}` — Get a single account with computed values (transactionCount)
- `PUT /api/accounts/{id}` — Update an account
- `DELETE /api/accounts/{id}` — Delete an account (fails if activities reference it)

Account types: `SECURITIES`, `CASH`, `DEPOSIT`, `LOAN`

### 2. Activities — Transaction CRUD (2 paths, 5 methods)

Activities record buy, sell, dividend, fee, interest, and item transactions.

- `GET /api/activities` — List all activities for the current user (supports filtering, sorting)
- `POST /api/activities` — Create an activity
- `GET /api/activities/{id}` — Get a single activity
- `PUT /api/activities/{id}` — Update an activity
- `DELETE /api/activities/{id}` — Delete an activity

Activity types: `BUY`, `SELL`, `DIVIDEND`, `FEE`, `INTEREST`, `ITEM`

### 3. Portfolio — Computed portfolio analytics (3 paths, 3 methods)

Read-only computed endpoints that aggregate activity data into portfolio metrics.

- `GET /api/portfolio/summary` — Portfolio summary: total value, gain/loss, performance %
- `GET /api/portfolio/holdings` — List current holdings with market value, gain/loss per position
- `GET /api/portfolio/performance` — Performance over time (total invested, current value, gain)

### 4. Holdings — Individual position details (1 path, 1 method)

- `GET /api/portfolio/holdings/{symbol}` — Detailed view of a single holding (quantity, averageCost, marketPrice, gain/loss)

### 5. Symbols — Asset lookup (2 paths, 2 methods)

- `GET /api/symbols` — Search/list available symbols
- `GET /api/symbols/{symbol}` — Get symbol details (name, currency, current price, sector)

### 6. Tags — Activity tagging (2 paths, 5 methods)

- `GET /api/tags` — List all tags for the current user
- `POST /api/tags` — Create a tag
- `GET /api/tags/{id}` — Get a single tag
- `PUT /api/tags/{id}` — Update a tag
- `DELETE /api/tags/{id}` — Delete a tag (removes from activities, doesn't delete activities)

### 7. Users — User profile (1 path, 2 methods)

- `GET /api/user` — Get the current user's profile (baseCurrency, dateCreated)
- `PUT /api/user` — Update user settings (baseCurrency)

### 8. Import/Export — Bulk operations (2 paths, 2 methods)

- `POST /api/import` — Import activities from JSON
- `GET /api/export` — Export all activities as JSON

### 9. Health — System status (1 path, 1 method)

- `GET /api/health` — Returns health status (no auth required)

---

**Totals: 16 paths, 26 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 16 paths / 26 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup (market data / symbols are hardcoded, not seed data)

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Mock Market Data

Since this is a self-contained benchmark, market data is mocked. The following symbols have fixed "current prices":

| Symbol | Name | Currency | Price | Sector |
|--------|------|----------|-------|--------|
| AAPL | Apple Inc. | USD | 150.00 | Technology |
| GOOGL | Alphabet Inc. | USD | 140.00 | Technology |
| MSFT | Microsoft Corp. | USD | 400.00 | Technology |
| AMZN | Amazon.com Inc. | USD | 180.00 | Consumer Cyclical |
| TSLA | Tesla Inc. | USD | 250.00 | Consumer Cyclical |
| NVDA | NVIDIA Corp. | USD | 800.00 | Technology |
| JPM | JPMorgan Chase | USD | 190.00 | Financial Services |
| VTI | Vanguard Total Stock Market ETF | USD | 220.00 | Index Fund |
| BND | Vanguard Total Bond Market ETF | USD | 75.00 | Bond |
| GLD | SPDR Gold Shares | USD | 185.00 | Commodities |

Exchange rates (to USD):
- USD = 1.0
- EUR = 1.08 (1 EUR = 1.08 USD)
- GBP = 1.27 (1 GBP = 1.27 USD)
- CHF = 1.12 (1 CHF = 1.12 USD)
- JPY = 0.0067 (1 JPY = 0.0067 USD)

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create users**: When a request comes in with `X-User-Id: <uuid>`, if no user with that ID exists, automatically create the user with `baseCurrency = "USD"`.

2. **Portfolio value calculation**:
   - Portfolio value = sum of (quantity × currentPrice) for all holdings + sum of cash account balances
   - Only holdings with quantity > 0 are included

3. **Holding quantity calculation**:
   - Quantity = sum of BUY quantities − sum of SELL quantities for that symbol (across all accounts)
   - A holding with quantity = 0 is not included in holdings list

4. **Average cost basis**:
   - averageCost = total cost of all BUY activities / total quantity bought
   - Total cost of a BUY = quantity × unitPrice + fee
   - Only BUY activities factor into average cost

5. **Gain/Loss per holding**:
   - unrealizedGain = (currentPrice − averageCost) × currentQuantity
   - unrealizedGainPercent = (currentPrice − averageCost) / averageCost × 100

6. **Portfolio summary calculations**:
   - `totalInvested` = sum of (quantity × unitPrice) for all BUY activities (excluding sold shares is NOT required — it's gross investment)
   - `currentValue` = sum of (holding quantity × current market price) for all holdings + sum of CASH account balances
   - `totalGain` = (holdings market value − totalInvested) + totalDividends + totalInterest − totalFees (cash positions are NOT included in gain)
   - `totalGainPercent` = (totalGain / totalInvested) × 100 (0 if totalInvested is 0)

7. **Dividends**: Add to totalDividends in summary, do NOT change holding quantity.

8. **Interest**: Treated like dividends for summary (adds to income). Does NOT change holding quantity.

9. **Fees**: Deducted from portfolio gain. Do NOT change holding quantity.

10. **ITEM type**: Represents non-tradable assets (real estate, collectibles). Has a unitPrice (current value) and quantity of 1. Included in portfolio value.

11. **Sell validation**: Cannot sell more shares than currently owned. If a SELL activity would make the holding quantity negative, return `400 Bad Request` with an error message.

12. **Account deletion**: Cannot delete an account that has activities referencing it. Return `400 Bad Request`.

13. **Currency handling**: All portfolio calculations are done in the user's `baseCurrency`. If a holding's currency differs from the user's base currency, convert using the exchange rates. Example: if user's baseCurrency is USD and holding is in EUR, multiply EUR value by 1.08 to get USD value.

14. **Activity fees**: Every activity can have a `fee` field (default 0). Fees are always in the activity's currency.

15. **Tags on activities**: Activities can have multiple tags (many-to-many). When creating/updating an activity, pass `tagIds` array. Tags are returned as objects with `id` and `name`.

16. **Import validation**: When importing activities, validate each activity. If any activity is invalid (missing required fields, invalid symbol for BUY/SELL), return `400 Bad Request` and import none (atomic).

17. **Export format**: Export returns all activities as a JSON array in the same format as the import accepts.

18. **Symbol lookup**: The `GET /api/symbols` endpoint supports a `query` parameter for searching by symbol or name (case-insensitive partial match). Returns all symbols if no query.

19. **Activity sorting**: `GET /api/activities` supports `sortBy` (field name) and `sortDirection` (`asc` or `desc`). Default sort is by `date` descending.

20. **Unique tag names per user**: A user cannot have two tags with the same name. Return `400 Bad Request` on duplicate.
