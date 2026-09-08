# Healthchecks — Backend Implementation Spec

## Overview

Healthchecks is a **cron job and background task monitoring service** (based on [Healthchecks](https://github.com/healthchecks/healthchecks), 10K★). Users create "checks" — monitors that expect periodic pings. If a ping doesn't arrive on time, the check transitions to "down" status. The service supports notification channels (email, webhook, slack) to alert users when checks go down.

The application is self-hosted and API-driven. A typical deployment monitors 10–500 cron jobs across multiple projects.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth with API key:
- `X-Api-Key`: A string identifying the project

Rules:
- The `X-Api-Key` header is required on all `/api/v1/` endpoints. If missing, return `401 Unauthorized`.
- **Ping endpoints** (`/ping/...`) do NOT require any authentication — they use the check's UUID directly in the URL.
- Trust the API key directly — no database lookup is required to verify it. The API key string itself acts as the project identifier.
- **Data scoping**: All checks, channels, integrations, and pings are scoped to the API key. Different API keys = different projects = completely isolated data.
- **Isolation**: A request with API key A must never see or modify data belonging to API key B. Attempting to access another project's check returns `403 Forbidden`.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (19 paths, 34 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Checks — CRUD for monitoring checks (6 paths, 10 methods)

The core entity. A check monitors one cron job or periodic task. Each check has a unique UUID `id`, a `name`, `tags` (space-separated string), scheduling configuration, and a computed `status`.

- `GET /api/v1/checks/` — List all checks in the project; optionally filter by `tag` query param
- `POST /api/v1/checks/` — Create a new check (body: name, tags, timeout, grace, schedule, tz, channels, unique, etc.)
- `GET /api/v1/checks/{check_id}` — Get a single check by UUID
- `POST /api/v1/checks/{check_id}` — Update a check (partial update; only fields present in body are changed)
- `DELETE /api/v1/checks/{check_id}` — Delete a check (returns the deleted check)
- `POST /api/v1/checks/{check_id}/pause` — Pause a check (sets status to "paused")
- `POST /api/v1/checks/{check_id}/resume` — Resume a paused check (sets status to "new")
- `GET /api/v1/checks/{check_id}/pings/` — List ping history for a check (most recent first)
- `GET /api/v1/checks/{check_id}/flips/` — List status flips; filterable by `start` and `end` timestamps
- `POST /api/v1/checks/{check_id}/channels/{channel_id}` — Assign a channel to a check
- `DELETE /api/v1/checks/{check_id}/channels/{channel_id}` — Remove a channel from a check

### 2. Pings — Record heartbeats for checks (4 paths, 5 methods)

Pings are the heartbeat signals sent by monitored jobs. Each ping updates the check's status and records a log entry. Ping endpoints do NOT require `X-Api-Key` — they use the check's UUID directly in the URL.

- `GET /ping/{check_id}` — Record a success ping (GET also works)
- `POST /ping/{check_id}` — Record a success ping
- `POST /ping/{check_id}/fail` — Record a failure ping (sets check to "down")
- `POST /ping/{check_id}/start` — Record a "job started" ping
- `POST /ping/{check_id}/log` — Record a log-only ping (does not change status)

### 3. Channels — CRUD for notification channels (2 paths, 5 methods)

Channels define how users get notified when a check changes status. Supported kinds: email, webhook, slack, pagerduty, opsgenie.

- `GET /api/v1/channels/` — List all channels in the project
- `POST /api/v1/channels/` — Create a new channel (body: kind, name, email/webhook_url)
- `GET /api/v1/channels/{channel_id}` — Get a single channel by UUID
- `PUT /api/v1/channels/{channel_id}` — Update a channel
- `DELETE /api/v1/channels/{channel_id}` — Delete a channel (returns the deleted channel)

### 4. Badges — Status badge endpoints (2 paths, 2 methods)

Return JSON status summaries for all checks or checks filtered by tag.

- `GET /api/v1/badges/` — List all available badge keys (one per unique tag + "*" for all)
- `GET /api/v1/badges/{tag}` — Get status badge for a specific tag (or "*" for all checks)

### 5. Integrations — Manage notification integrations (2 paths, 5 methods)

Higher-level integration management that wraps channel configuration with additional metadata and an `is_active` flag.

- `GET /api/v1/integrations/` — List all integrations
- `POST /api/v1/integrations/` — Create a new integration
- `GET /api/v1/integrations/{integration_id}` — Get a single integration
- `PUT /api/v1/integrations/{integration_id}` — Update an integration
- `DELETE /api/v1/integrations/{integration_id}` — Delete an integration

### 6. Project Info (1 path, 1 method)

- `GET /api/v1/project/` — Return project-level information (api_key, name, check_count, channel_count)

---

**Totals: 19 paths, ~34 methods across 6 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all paths and methods** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Check status logic**: A check's `status` is computed based on its last ping time and scheduling configuration:
   - `"new"` — never pinged (or just resumed)
   - `"up"` — last ping was a success and within the expected period
   - `"down"` — overdue past grace period OR last ping was a failure
   - `"grace"` — overdue but still within grace period
   - `"paused"` — manually paused via the pause endpoint

2. **Status determination for simple checks** (kind="simple"): The check has `timeout` (seconds) and `grace` (seconds). After a successful ping:
   - If `now < last_ping + timeout` → status is "up"
   - If `last_ping + timeout <= now < last_ping + timeout + grace` → status is "grace"
   - If `now >= last_ping + timeout + grace` → status is "down"

3. **Status determination for cron checks** (kind="cron"): The check has a `schedule` (cron expression) and `grace` (seconds). After a successful ping, compute the NEXT expected ping time from the cron schedule:
   - If `now < next_expected` → status is "up"
   - If `next_expected <= now < next_expected + grace` → status is "grace"
   - If `now >= next_expected + grace` → status is "down"

4. **Ping effects on status**:
   - Success ping → status becomes "up", `last_ping` updated, `n_pings` incremented
   - Failure ping → status becomes "down" immediately, `last_ping` updated, `n_pings` incremented
   - Start ping → `last_start` updated, `n_pings` incremented, status NOT changed
   - Log ping → `n_pings` incremented, status NOT changed, `last_ping` NOT updated

5. **Check kind determination**: A check is "simple" if it has a `timeout` value. A check is "cron" if it has a `schedule` value (a valid 5-field cron expression). Default kind is "simple" with timeout=86400 (1 day) and grace=3600 (1 hour).

6. **Pause/Resume**:
   - Pausing sets status to "paused" and clears `last_start`
   - Resuming a paused check sets status to "new" and clears `last_ping`, `last_start`
   - Resuming a non-paused check returns `409 Conflict`
   - Pausing an already-paused check is idempotent (returns 200)

7. **Channel assignment via check creation/update**: When creating or updating a check, you can pass `channels` as a string:
   - `"*"` = assign all current project channels
   - `""` = assign no channels (clear all)
   - Comma-separated UUIDs = assign specific channels
   - If `channels` field is omitted from update, don't change current assignments

8. **Unique check lookup (upsert)**: When creating a check with a `unique` field (array of field names like `["name", "tags"]`), first look for an existing check matching ALL specified fields. If found, update it instead of creating a new one. Return `200` for update, `201` for create.

9. **Tags**: Tags are stored as a single space-separated string. The `tag` query parameter on `GET /api/v1/checks/` filters to only checks that contain the specified tag (substring match within space-separated list).

10. **Badge status**: Badge endpoints aggregate check statuses. For a tag, look at all checks with that tag:
    - If any check is "down" → badge status is "down"
    - Else if any check is "grace" → badge status is "late"
    - Else → badge status is "up"

11. **Flip recording**: Every time a check's status changes (e.g., from "new" to "up", or "up" to "down"), record a flip with the timestamp and the new state (up=1 for up/new, up=0 for down/paused).

12. **Ping history**: `GET /api/v1/checks/{id}/pings/` returns pings in reverse chronological order (most recent first). Each ping records: type (success/fail/start/log), timestamp (date), ping number (n), scheme, remote_addr, method, optional body text, and optional duration.

13. **Duration calculation**: If a success or fail ping is preceded by a start ping, compute the duration as the elapsed time between start and success/fail. Store as `last_duration` on the check.

14. **Validation**:
    - `timeout` must be between 60 and 31536000 (inclusive). Otherwise return 400.
    - `grace` must be between 60 and 31536000 (inclusive). Otherwise return 400.
    - `schedule` must be a valid 5-field cron expression. Otherwise return 400.
    - Channel `kind` is required and must be one of: email, webhook, slack, pagerduty, opsgenie. Otherwise return 400.
