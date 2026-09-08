# Invoice Ninja — Invoicing & Quoting Platform

## Overview

A backend API for freelancers and small businesses to manage clients, create invoices/quotes, track payments, log expenses, and handle time tracking. Inspired by [Invoice Ninja](https://github.com/invoiceninja/invoiceninja).

## Tech Stack

Your choice.

## Authentication

- All endpoints require an `X-Api-Key` header.
- The header value is trusted directly as the company identifier — no database lookup needed.
- Missing or empty `X-Api-Key` header → `401 Unauthorized`.
- All data is scoped to the company identified by the API key. Different API keys cannot see each other's data.

## Endpoint Groups

### Clients (`/api/clients`)
CRUD for business clients. Fields: name, email, phone, address, currency. Two computed fields:
- `balance`: sum of all unpaid invoice balances for this client
- `paid_to_date`: sum of all payment amounts applied to this client's invoices

### Products (`/api/products`)
CRUD for product/service catalog. Fields: name, description, price, quantity_default, tax_name, tax_rate.

### Invoices (`/api/invoices`)
CRUD for invoices. Fields: client_id, number (auto-generated), status, date, due_date, line_items, discount, discount_type, tax_name, tax_rate, amount (computed), balance (computed), paid_to_date (computed).

Actions:
- `POST /api/invoices/{id}/actions/mark_sent` — changes status from "draft" to "sent"
- `POST /api/invoices/{id}/actions/mark_paid` — creates a payment for the full balance, status → "paid"

### Quotes (`/api/quotes`)
CRUD for quotes. Similar to invoices but with different statuses.

Actions:
- `POST /api/quotes/{id}/actions/approve` — status → "approved"
- `POST /api/quotes/{id}/actions/convert_to_invoice` — creates a new invoice from the quote, links them, quote status → "converted"

### Payments (`/api/payments`)
CRUD for payments. Fields: client_id, amount, date, invoices (array of {invoice_id, amount} pairs), refunded.

Actions:
- `POST /api/payments/{id}/actions/refund` — refund a specific amount; updates invoice balances accordingly

### Expenses (`/api/expenses`)
CRUD for business expenses. Fields: vendor, category, amount, date, currency, invoice_id (when billed to a client via invoice).

### Recurring Invoices (`/api/recurring_invoices`)
CRUD for recurring invoice templates. Fields: client_id, frequency (weekly/monthly/quarterly/yearly), start_date, remaining_cycles, line_items, discount, discount_type, tax_name, tax_rate, status (active/paused/completed).

### Tasks (`/api/tasks`)
CRUD for time tracking. Fields: client_id, project_id, description, time_log (array of [start, end] unix timestamp pairs), rate, amount (computed: total_hours * rate), status (active/invoiced).

### Projects (`/api/projects`)
CRUD for project management. Fields: name, client_id, budgeted_hours, task_rate, total_hours (computed from tasks), tasks (list of task IDs).

## Business Rules

### Invoice Numbering
- Invoices are auto-numbered with format `INV-XXXX` (zero-padded 4 digits).
- First invoice is `INV-0001`, second is `INV-0002`, etc.
- Numbers are scoped per company (each API key has its own counter).
- Quote numbering follows same pattern with prefix `QTE-XXXX`.

### Invoice Amount Calculation
```
line_total = quantity * unit_cost
subtotal = sum(line_items[].line_total)
discount_amount = discount if discount_type == "amount" else subtotal * discount / 100
tax_amount = (subtotal - discount_amount) * tax_rate / 100
amount = subtotal - discount_amount + tax_amount
```

### Invoice Balance
```
balance = amount - paid_to_date
paid_to_date = sum of all payment amounts applied to this invoice
```

### Client Computed Fields
```
client.balance = sum(invoice.balance for invoice in client's invoices where status not in ["draft", "cancelled"])
client.paid_to_date = sum(payment.amount - payment.refunded for payment in client's payments)
```

### Payment Application
- A payment specifies `invoices`: an array of `{invoice_id, amount}` objects.
- Each entry reduces that invoice's balance by the specified amount.
- If an invoice's balance reaches 0, its status changes to "paid".
- If an invoice's balance is reduced but still > 0, its status changes to "partial".
- The sum of all invoice amounts in a payment must equal the payment's `amount` field.

### Payment Refund
- `POST /api/payments/{id}/actions/refund` with body `{"amount": X}`.
- Increases `payment.refunded` by X. Cannot exceed original payment amount.
- Increases the corresponding invoice balances (applied proportionally to the invoices in the payment).
- If a "paid" invoice gets balance > 0 after refund, status reverts to "partial" or "sent".

### Quote to Invoice Conversion
- Creates a new invoice with the same line_items, discount, discount_type, tax_name, tax_rate.
- Sets invoice client_id = quote client_id.
- Quote status → "converted".
- Quote gets `invoice_id` field linking to the created invoice.
- Cannot convert a quote that is already "converted" or "rejected".

### Recurring Invoices
- `remaining_cycles`: number of invoices left to generate. -1 means infinite.
- Status: "active" (will generate), "paused" (won't generate), "completed" (cycles exhausted).
- When `remaining_cycles` reaches 0, status → "completed".

### Task Time Calculation
- `time_log` is an array of `[start_timestamp, end_timestamp]` pairs (unix seconds).
- `total_hours = sum((end - start) / 3600 for [start, end] in time_log)` (only for entries where end > 0).
- `amount = total_hours * rate`.

### Project Computed Fields
- `total_hours`: sum of hours from all tasks linked to this project.

### Deletion Rules
- Deleting a client also deletes all their invoices, quotes, payments, expenses, tasks, projects.
- Deleting an invoice removes payment applications to that invoice (but not the payment itself).
- Deleting a project does NOT delete tasks (just unlinks them: sets project_id to null).

### Pagination
- All list endpoints support `per_page` (default 20, max 100) and `page` (default 1) query parameters.
- Response format for list endpoints:
```json
{
  "data": [...],
  "meta": {
    "current_page": 1,
    "per_page": 20,
    "total": 50,
    "total_pages": 3
  }
}
```

### Error Format
All errors return:
```json
{
  "error": "Description of the error"
}
```

### Status Codes
- GET (success): 200
- POST (created): 201
- PUT (updated): 200
- DELETE (success): 200 with `{"message": "deleted"}`
- Not found: 404
- Validation error: 422
- Unauthorized: 401
