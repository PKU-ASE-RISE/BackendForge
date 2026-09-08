# Django CRM — Backend Implementation Spec

## Overview

A **Customer Relationship Management (CRM)** system (inspired by [Django-CRM](https://github.com/MicroPyramid/Django-CRM), 2.1K stars). Manage contacts, companies, leads, opportunities (deals), activities, and pipeline stages. Supports multi-user organizations with shared data visibility within an org.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID identifying the user
- `X-Org-Id`: UUID identifying the organization

Rules:
- Both headers are required on **all** endpoints except `GET /health`.
- If either header is missing, return `401 Unauthorized` with body `{"detail": "Missing authentication headers"}`.
- Trust header values directly — no database lookup needed to verify users/orgs.
- **Data scoping**: All data is scoped to the organization (`X-Org-Id`). Multiple users in the same org can see and modify the same data.
- The `X-User-Id` is recorded as the creator/owner of resources, and used for `assigned_to` validation.
- When a user makes their first request, implicitly register them as a member of that org (for `assigned_to` validation purposes).

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (35 endpoints across 9 groups). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Contacts — people in the CRM (5 endpoints)

- `GET /contacts` — List contacts (supports `?search=` for name/email, `?tag=` filter)
- `POST /contacts` — Create a contact (201 Created)
- `GET /contacts/{id}` — Get a single contact
- `PUT /contacts/{id}` — Update a contact
- `DELETE /contacts/{id}` — Delete a contact (also deletes linked activities)

### 2. Companies — organizations/accounts (5 endpoints)

- `GET /companies` — List companies (supports `?search=` for name/domain)
- `POST /companies` — Create a company (201 Created)
- `GET /companies/{id}` — Get a single company
- `PUT /companies/{id}` — Update a company
- `DELETE /companies/{id}` — Delete a company (nullifies company_id on contacts)

### 3. Leads — potential customers (6 endpoints)

- `GET /leads` — List leads (supports `?status=` filter, `?assigned_to=` filter)
- `POST /leads` — Create a lead (201 Created)
- `GET /leads/{id}` — Get a single lead
- `PUT /leads/{id}` — Update a lead (status transitions enforced)
- `DELETE /leads/{id}` — Delete a lead
- `POST /leads/{id}/convert` — Convert a lead to an opportunity (creates opportunity, changes status to "converted")

### 4. Opportunities — deals in the pipeline (5 endpoints)

- `GET /opportunities` — List opportunities (supports `?stage=` filter, `?assigned_to=` filter)
- `POST /opportunities` — Create an opportunity (201 Created)
- `GET /opportunities/{id}` — Get a single opportunity
- `PUT /opportunities/{id}` — Update an opportunity (stage transitions enforced)
- `DELETE /opportunities/{id}` — Delete an opportunity

### 5. Activities — tasks, calls, meetings, emails (5 endpoints)

- `GET /activities` — List activities (supports `?type=` filter, `?completed=` filter)
- `POST /activities` — Create an activity (201 Created)
- `GET /activities/{id}` — Get a single activity
- `PUT /activities/{id}` — Update an activity
- `DELETE /activities/{id}` — Delete an activity

### 6. Pipeline — aggregated view (1 endpoint)

- `GET /pipeline` — Returns deals grouped by stage with aggregated values (sum of value*probability/100 per stage)

### 7. Comments — notes on leads/opportunities (3 endpoints)

- `GET /comments?entity_type=lead&entity_id={id}` — List comments for an entity
- `POST /comments` — Add a comment to a lead or opportunity (201 Created)
- `DELETE /comments/{id}` — Delete a comment

### 8. Tags — reusable labels (3 endpoints)

- `GET /tags` — List all tags in the org
- `POST /tags` — Create a tag (201 Created; dedup by name within org)
- `DELETE /tags/{id}` — Delete a tag (removes from all contacts/leads)

### 9. Health (1 endpoint)

- `GET /health` — Returns `{"status": "healthy"}` (no auth required)

---

**Totals: 34 endpoints across 9 groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 34 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

### Lead Status Transitions

Valid statuses: `new`, `contacted`, `qualified`, `lost`, `converted`.

Allowed transitions:
- `new` → `contacted`
- `contacted` → `qualified`
- `qualified` → `converted` (only via POST /leads/{id}/convert)
- `qualified` → `lost`
- `contacted` → `lost`
- `new` → `lost`

Cannot go backwards (e.g., `contacted` → `new` is invalid). Cannot skip forward (e.g., `new` → `qualified` is invalid). The only way to reach `converted` is through the `/convert` endpoint. Attempting an invalid transition via PUT returns `422 Unprocessable Entity` with `{"detail": "Invalid status transition from '{current}' to '{target}'"}`.

### Opportunity Stage Transitions

Valid stages (in pipeline order): `prospecting`, `proposal`, `negotiation`, `closed_won`, `closed_lost`.

Rules:
- Must follow pipeline order: prospecting → proposal → negotiation → closed_won
- Cannot skip stages (e.g., prospecting → negotiation is invalid)
- Exception: ANY stage can transition to `closed_lost` (deal can be lost at any point)
- Cannot transition FROM `closed_won` or `closed_lost` (terminal states)
- Attempting an invalid transition returns `422 Unprocessable Entity` with `{"detail": "Invalid stage transition from '{current}' to '{target}'"}`

### Lead Conversion

`POST /leads/{id}/convert`:
- Lead must be in status `qualified` to be converted. Otherwise return `422` with `{"detail": "Lead must be in 'qualified' status to convert"}`.
- Creates a new opportunity with:
  - `title`: "Opportunity from {lead contact's name}" (use the contact's name linked to the lead)
  - `lead_id`: the converted lead's ID
  - `contact_id`: the lead's contact_id
  - `stage`: "prospecting"
  - `value`: copied from lead's value (or 0 if null)
  - `probability`: 10
  - `close_date`: null
  - `assigned_to`: copied from lead's assigned_to
  - `created_by`: the requesting user's ID
- Updates the lead's status to `converted`
- Returns the created opportunity (201 Created)

### Pipeline Aggregation

`GET /pipeline` returns an object with stages as keys, each containing:
- `count`: number of opportunities in that stage
- `total_value`: sum of `value` for opportunities in that stage
- `weighted_value`: sum of `(value * probability / 100)` for opportunities in that stage

All 5 stages are always present in the response (with zeros if empty). Only non-terminal stages (prospecting, proposal, negotiation) plus closed_won and closed_lost are included.

### Assigned-To Validation

The `assigned_to` field on leads and opportunities must be a valid user ID (UUID) that has been seen in the org (i.e., has made at least one request with that `X-User-Id` and matching `X-Org-Id`). If invalid, return `422 Unprocessable Entity` with `{"detail": "assigned_to user is not a member of this organization"}`.

`assigned_to` is optional (nullable) — omitting it or setting to null is always valid.

### Tag Deduplication

Tags are reused by name within an org:
- `POST /tags` with a name that already exists in the org returns the existing tag (201 Created, idempotent).
- Tags are linked to contacts and leads via the `tags` field (array of tag names).
- When creating/updating a contact or lead with tags, any tag name that doesn't exist gets auto-created.
- Deleting a tag removes it from all contacts and leads that reference it.

### Activity Due Date Validation

When creating a new activity (POST), `due_date` must not be in the past (before today's date at midnight UTC). Return `422 Unprocessable Entity` with `{"detail": "due_date cannot be in the past"}` if violated.

When updating an existing activity (PUT), the due_date restriction does NOT apply (allows rescheduling past-due items).

### Cascade / Nullification Rules

- Deleting a **contact**: deletes all activities linked to that contact; nullifies `contact_id` on leads.
- Deleting a **company**: nullifies `company_id` on contacts linked to that company.
- Deleting a **lead**: deletes all activities and comments linked to that lead.
- Deleting an **opportunity**: deletes all activities and comments linked to that opportunity.
- Deleting a **tag**: removes the tag from all contacts/leads that reference it.

### Search Behavior

- `GET /contacts?search=X` — searches in `first_name`, `last_name`, and `email` (case-insensitive substring match)
- `GET /companies?search=X` — searches in `name` and `domain` (case-insensitive substring match)
- `GET /contacts?tag=X` — returns contacts that have tag with name X

### ID Format

All entity IDs are UUIDs (v4), generated server-side.
