# Solidtime — Backend Implementation Spec

## Overview

Solidtime is a **modern time-tracking application** (based on [solidtime](https://github.com/solidtime-io/solidtime), 4K+ stars). Organizations track time entries for projects, assign tasks to team members, and generate reports. It supports multi-organization scoping, billable hours, running timers, and aggregate reporting.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified from real OAuth):

- `X-User-Id`: UUID identifying the authenticated user
- `X-Org-Id`: UUID identifying the organization context

Rules:
- Both headers are required on **all** endpoints.
- If either header is missing, return `401 Unauthorized`.
- Trust header values directly — no database lookup required for authentication. If the user/org combination doesn't exist in the system, auto-create both (the user becomes `owner` of that org).
- **Data scoping**: All data is scoped to the organization (`X-Org-Id`). Users can only see/modify data within their current organization.
- **Member check**: The user identified by `X-User-Id` must be a member of the organization identified by `X-Org-Id`. If not a member, auto-create a membership with role `member`.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (34 endpoints across 8 resource groups). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Organizations (2 endpoints)

- `GET /api/v1/organizations/current` — Get the current organization details
- `PUT /api/v1/organizations/current` — Update the current organization (name, billable_rate)

### 2. Members (4 endpoints)

Members are users within an organization with a specific role and hourly rate.

- `GET /api/v1/members` — List all members in the current org
- `POST /api/v1/members` — Invite/add a member (user_id, role, billable_rate)
- `PUT /api/v1/members/{id}` — Update a member (role, billable_rate)
- `DELETE /api/v1/members/{id}` — Remove a member from the org

### 3. Clients (4 endpoints)

Clients are entities that projects can be billed to.

- `GET /api/v1/clients` — List all clients (supports `archived` filter)
- `POST /api/v1/clients` — Create a client (name, email, address)
- `PUT /api/v1/clients/{id}` — Update a client
- `DELETE /api/v1/clients/{id}` — Archive/delete a client

### 4. Projects (5 endpoints)

Projects group time entries and belong to an organization, optionally linked to a client.

- `GET /api/v1/projects` — List all projects (supports `archived` filter)
- `POST /api/v1/projects` — Create a project (name, color, client_id, is_billable)
- `GET /api/v1/projects/{id}` — Get a single project
- `PUT /api/v1/projects/{id}` — Update a project
- `DELETE /api/v1/projects/{id}` — Archive/delete a project

### 5. Tasks (4 endpoints)

Tasks belong to a project and track estimated vs actual time.

- `GET /api/v1/tasks` — List tasks (filter by `project_id`, `done`)
- `POST /api/v1/tasks` — Create a task (name, project_id, estimated_seconds)
- `PUT /api/v1/tasks/{id}` — Update a task (name, done, estimated_seconds)
- `DELETE /api/v1/tasks/{id}` — Delete a task

### 6. Tags (4 endpoints)

Tags are org-scoped labels attached to time entries.

- `GET /api/v1/tags` — List all tags
- `POST /api/v1/tags` — Create a tag (name)
- `PUT /api/v1/tags/{id}` — Update a tag (name)
- `DELETE /api/v1/tags/{id}` — Delete a tag

### 7. Time Entries (7 endpoints)

Time entries are the core entity — tracking work periods.

- `GET /api/v1/time-entries` — List time entries (filter by project_id, task_id, billable, start/end range)
- `POST /api/v1/time-entries` — Create a time entry (start, end, description, project_id, task_id, billable, tag_ids)
- `GET /api/v1/time-entries/{id}` — Get a single time entry
- `PUT /api/v1/time-entries/{id}` — Update a time entry
- `DELETE /api/v1/time-entries/{id}` — Delete a time entry
- `POST /api/v1/time-entries/start` — Start a new timer (creates entry with end=null, auto-stops previous)
- `PUT /api/v1/time-entries/{id}/stop` — Stop a running timer (sets end timestamp)

### 8. Reports (4 endpoints)

Aggregated time data for analytics.

- `GET /api/v1/reports/time` — Total time summary with filters
- `GET /api/v1/reports/projects` — Time grouped by project
- `GET /api/v1/reports/members` — Time grouped by member
- `GET /api/v1/reports/daily` — Time grouped by day

---

**Totals: 34 endpoints across 8 resource groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 34 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create org + membership**: When a request comes in with `X-User-Id` and `X-Org-Id`, if the org doesn't exist, create it (with a default name "My Organization" and null billable_rate). If the user is not a member of that org, create a membership with role `owner` (if the org was just created) or role `member` (if the org already existed).

2. **Running timer**: A time entry with `end = null` is a "running timer". Only ONE running timer per user per organization is allowed. Starting a new timer (via `POST /api/v1/time-entries/start`) automatically stops any currently running timer for that user (sets `end` to the new timer's `start` time).

3. **Duration computation**: For completed entries (end != null), duration = end - start in seconds. For running timers (end = null), duration is computed as current_time - start. The `duration` field in responses is always an integer (seconds).

4. **Billable amount**: For billable time entries, the amount = (duration_seconds / 3600) × member.billable_rate. If member.billable_rate is null, fall back to organization.billable_rate. If both are null, amount = 0. The `billable_amount` field in responses is a float (currency units).

5. **Archived projects**: Cannot create new time entries for archived projects. Return `422 Unprocessable Entity`. Existing time entries for archived projects remain accessible.

6. **Archived clients**: Cannot create new projects for archived clients. Return `422 Unprocessable Entity`.

7. **Reports aggregation**: Reports sum `duration` (in seconds) across matching time entries. Filters: `start` (ISO datetime, entries starting on or after), `end` (ISO datetime, entries starting before), `project_id`, `member_id`, `billable` (boolean). Running timers use current time for duration calculation in reports.

8. **Member roles**: Three roles: `owner`, `admin`, `member`. Owners cannot be removed from the org. Only one owner per org. Cannot change the owner's role.

9. **Tag association**: Time entries can have multiple tags (many-to-many). Tags are passed as `tag_ids` array on create/update.

10. **Task estimated time**: `estimated_seconds` on a task. Reports and GET task response include `spent_seconds` (sum of all time entry durations for that task).

11. **Project color**: A hex color string (e.g., "#FF5733"). Must be valid 7-char hex color format.

12. **Cascade behavior**:
    - Deleting a project sets `project_id = null` on its time entries (soft disassociation), and deletes all tasks for that project.
    - Deleting a client sets `client_id = null` on its projects.
    - Deleting a tag removes it from all time entry associations.
    - Removing a member does NOT delete their time entries (they remain attributed to that user_id).

13. **Unique constraints**:
    - Tag names must be unique within an organization.
    - Project names must be unique within an organization.
    - Client names must be unique within an organization.
    - A user can only be a member of an org once.

14. **Stop timer**: `PUT /api/v1/time-entries/{id}/stop` sets the `end` field to the provided timestamp. Returns 422 if the entry already has an `end` (not a running timer). The request body must include the `end` timestamp.

15. **Time entry validation**: `start` is required. If `end` is provided, it must be after `start`. Returns `422 Unprocessable Entity` on validation failure.
