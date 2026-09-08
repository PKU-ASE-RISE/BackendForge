# Lago — Backend Implementation Spec

## Overview

Lago is a **usage-based billing and subscription management API** (based on [Lago](https://github.com/getlago/lago), 10K+ stars). It handles customer management, plan definitions, usage metering, subscription lifecycle, invoice generation, prepaid wallets, and coupon discounts. Typical deployments handle thousands of billing events across multiple customers and plans.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based authentication:

- `X-Api-Key`: API key identifying the organization

Rules:
- The `X-Api-Key` header is required on **all** endpoints.
- If the header is missing or empty, return `401 Unauthorized` with body `{"error": "Unauthorized"}`.
- Trust header values directly — the key IS the organization identifier. If an organization with that key doesn't exist, **auto-create** it.
- **Data scoping**: All data (customers, plans, metrics, subscriptions, events, invoices, wallets, coupons) is scoped to the authenticated organization. An organization can only see/modify its own data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (37 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Customers — customer management (5 endpoints)

Customers represent the entities being billed. They are identified by an `external_id` unique within the organization.

- `POST /customers` — Create a customer (body: `external_id`, `name`, `email`, `currency`, `timezone`, `billing_address`)
- `GET /customers` — List all customers (supports `page`, `per_page` pagination)
- `GET /customers/{external_id}` — Get a customer by external_id
- `PUT /customers/{external_id}` — Update a customer
- `DELETE /customers/{external_id}` — Delete a customer (also deletes subscriptions, wallets)

### 2. Plans — billing plan definitions (4 endpoints)

Plans define what is billed and at what interval.

- `POST /plans` — Create a plan (body: `name`, `code`, `interval`, `amount_cents`, `currency`, `pay_in_advance`, `trial_period_days`)
- `GET /plans` — List all plans (supports `page`, `per_page`)
- `GET /plans/{code}` — Get a plan by code
- `PUT /plans/{code}` — Update a plan
- `DELETE /plans/{code}` — Delete a plan (cannot delete if active subscriptions exist)

### 3. Billable Metrics — usage metric definitions (4 endpoints)

Billable metrics define what usage events are tracked and how they are aggregated.

- `POST /billable_metrics` — Create a metric (body: `name`, `code`, `aggregation_type`, `field_name`)
- `GET /billable_metrics` — List all metrics (supports `page`, `per_page`)
- `GET /billable_metrics/{code}` — Get a metric by code
- `DELETE /billable_metrics/{code}` — Delete a metric (cannot delete if charges reference it)

### 4. Plan Charges — attach charges to plans (3 endpoints)

Charges connect a billable metric to a plan with a specific pricing model.

- `POST /plans/{plan_code}/charges` — Add a charge to a plan (body: `billable_metric_code`, `charge_model`, `properties`)
- `GET /plans/{plan_code}/charges` — List charges for a plan
- `DELETE /plans/{plan_code}/charges/{charge_id}` — Remove a charge from a plan

### 5. Subscriptions — customer subscription lifecycle (5 endpoints)

Subscriptions connect customers to plans and drive billing.

- `POST /subscriptions` — Create a subscription (body: `external_customer_id`, `plan_code`, `billing_time`, `started_at`)
- `GET /subscriptions` — List subscriptions (supports `page`, `per_page`, filter by `external_customer_id`, `plan_code`, `status`)
- `GET /subscriptions/{id}` — Get a subscription by ID
- `PUT /subscriptions/{id}` — Update a subscription (change `ending_at`)
- `DELETE /subscriptions/{id}` — Terminate a subscription (sets status to terminated, sets `terminated_at`)

### 6. Events — usage event ingestion (3 endpoints)

Events record customer usage of billable metrics.

- `POST /events` — Ingest a usage event (body: `transaction_id`, `external_customer_id`, `code`, `timestamp`, `properties`)
- `GET /events` — List events (supports `page`, `per_page`, filter by `external_customer_id`, `code`)
- `GET /events/{transaction_id}` — Get an event by transaction_id

### 7. Invoices — billing output (4 endpoints)

Invoices are generated from subscriptions and usage. They can also be manually triggered.

- `POST /invoices/generate` — Manually generate an invoice for a subscription (body: `subscription_id`)
- `GET /invoices` — List invoices (supports `page`, `per_page`, filter by `external_customer_id`, `status`)
- `GET /invoices/{id}` — Get an invoice by ID (includes line items)
- `PUT /invoices/{id}/void` — Void an invoice (only finalized invoices can be voided)

### 8. Wallets — prepaid credits (5 endpoints)

Wallets allow customers to have prepaid balances that offset invoice amounts.

- `POST /wallets` — Create a wallet for a customer (body: `external_customer_id`, `currency`, `name`, `paid_credits`, `granted_credits`)
- `GET /wallets` — List wallets (supports `page`, `per_page`, filter by `external_customer_id`)
- `GET /wallets/{id}` — Get a wallet by ID
- `POST /wallets/{id}/top_up` — Top up a wallet (body: `paid_credits`, `granted_credits`)
- `PUT /wallets/{id}` — Update a wallet (body: `name`, `expiration_at`)

### 9. Coupons — discount management (4 endpoints)

Coupons provide discounts on invoices.

- `POST /coupons` — Create a coupon (body: `name`, `code`, `coupon_type`, `amount_cents` or `percentage_rate`, `frequency`, `expiration_at`)
- `GET /coupons` — List coupons (supports `page`, `per_page`)
- `GET /coupons/{code}` — Get a coupon by code
- `DELETE /coupons/{code}` — Delete a coupon

---

**Totals: 37 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 37 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Organization auto-create**: When a request comes in with `X-Api-Key: somevalue`, if no organization with that key exists, automatically create it.

2. **Customer external_id uniqueness**: Within an organization, `external_id` must be unique. Return `409 Conflict` on duplicate.

3. **Plan code uniqueness**: Within an organization, plan `code` must be unique. Return `409 Conflict` on duplicate.

4. **Metric code uniqueness**: Within an organization, billable metric `code` must be unique. Return `409 Conflict` on duplicate.

5. **Coupon code uniqueness**: Within an organization, coupon `code` must be unique. Return `409 Conflict` on duplicate.

6. **Event idempotency**: The `transaction_id` field is globally unique within an organization. If an event with the same `transaction_id` is submitted again, return `200 OK` (not an error) but do NOT create a duplicate event. The original event is returned.

7. **Subscription lifecycle**:
   - New subscriptions start with status `active` (if `started_at` is in the past or now) or `pending` (if `started_at` is in the future).
   - Terminating a subscription sets its status to `terminated` and records `terminated_at` as the current time.
   - Only `active` or `pending` subscriptions can be terminated. Attempting to terminate an already terminated subscription returns `400 Bad Request`.

8. **Plan deletion constraint**: A plan cannot be deleted if there are active or pending subscriptions using it. Return `400 Bad Request`.

9. **Metric deletion constraint**: A billable metric cannot be deleted if any plan charge references it. Return `400 Bad Request`.

10. **Usage aggregation**: When generating an invoice, aggregate events by their metric `code` for the billing period:
    - `count`: Count the number of events
    - `sum`: Sum the value of `field_name` from event properties
    - `max`: Maximum value of `field_name` from event properties
    - `unique_count`: Count distinct values of `field_name` from event properties

11. **Charge calculation models**:
    - `standard`: `quantity * rate` (rate from `properties.amount`)
    - `graduated`: Tiered pricing — `properties.graduated_ranges` is an array of `{from_value, to_value, per_unit_amount, flat_amount}`. Apply each tier sequentially.
    - `package`: Package pricing — bill per package of N units. `properties.package_size` and `properties.amount` define the pricing. Partial packages count as full.
    - `percentage`: `quantity * properties.rate / 100`

12. **Invoice generation logic**: When `POST /invoices/generate` is called:
    - Find the subscription and its plan
    - Create an invoice with status `draft`
    - Add a line item for the plan's base amount (the plan's `amount_cents`)
    - For each charge on the plan, aggregate usage events for that subscription's customer since the subscription's `started_at` (or last invoice date) up to now
    - Calculate the charge amount using the charge model and add as a line item
    - Sum all line items for `amount_cents` on the invoice
    - Apply wallet credits if the customer has a wallet with balance — deduct from invoice `amount_cents`, reduce wallet `balance_cents`
    - Apply coupon if the customer has an active applied coupon — reduce invoice `amount_cents`
    - Finalize: set invoice status to `finalized`

13. **Wallet balance**:
    - `balance_cents` = `paid_credits` + `granted_credits` (in cents, 1 credit = 100 cents)
    - Top-up adds to the balance
    - Invoice generation deducts from wallet balance (cannot go below 0)

14. **Coupon application**:
    - `coupon_type: "fixed_amount"` — deduct `amount_cents` from invoice
    - `coupon_type: "percentage"` — deduct `percentage_rate`% from invoice total
    - `frequency: "once"` — coupon is consumed after first use
    - `frequency: "recurring"` — coupon applies to every invoice until expiration

15. **Pagination**: All list endpoints support `page` (default 1) and `per_page` (default 20, max 100). Response includes a `meta` object with `current_page`, `total_pages`, `total_count`, `next_page` (null if last page), `prev_page` (null if first page).

16. **Timestamps**: All created resources include `created_at` (ISO 8601 timestamp). Updated resources also include `updated_at`.

17. **Cascade deletes**:
    - Deleting a customer deletes their subscriptions and wallets
    - Terminating is preferred over deleting for subscriptions (to maintain audit trail)

18. **Currency**: Monetary amounts are always in cents (integer). The `currency` field is a 3-letter ISO code (e.g., "USD", "EUR").
