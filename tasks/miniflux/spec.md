# Miniflux — Backend Implementation Spec

## Overview

Miniflux is a **minimalist RSS feed reader** (based on [Miniflux](https://github.com/miniflux/v2), 9.1K★). Users subscribe to RSS/Atom feeds, read entries (articles), organize feeds into categories, star/bookmark entries, and manage read/unread status. Supports multi-user with admin management, OPML import/export, and feed discovery.

The application is self-hosted, designed for simplicity and speed. A typical user subscribes to 50–500 feeds with thousands of entries.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth using API key:
- `X-Auth-Token`: API key string identifying the user

Rules:
- The header is required on every request (except `/healthcheck`). If missing, return `401 Unauthorized`.
- **Trust the token directly as a user identifier** — no database lookup required to validate the key. The token value IS the user's API key; use it to identify which user is making the request. If no user exists with that key, auto-create a user record.
- **Data scoping**: Feeds, entries, and categories are scoped to the authenticated user. Each user only sees their own data.
- **Admin**: The first user created (or a user with `is_admin=true`) can manage other users. Non-admin users cannot access user management endpoints (except `/v1/me`).

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (35 paths, ~45 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

### Important: Feed Fetching is Mocked

This is a **backend-only** implementation. Do NOT actually fetch RSS feeds from the internet. Instead:
- Feeds are created with metadata (URL, title, category) via the API
- Entries are created via `POST /v1/feeds/{id}/entries` (simulating what a feed fetcher would produce)
- Feed refresh endpoints (`PUT /v1/feeds/{id}/refresh`, `PUT /v1/feeds/refresh`) should return success but don't need to fetch anything
- `POST /v1/discover` accepts a URL and returns a mock list of discovered feeds (just echo back the URL as a feed suggestion)

---

### 1. Categories — Organize feeds (5 paths, 6 methods)

- `GET /v1/categories` — List all categories for the user; supports `?counts=true` to include feed/entry counts
- `POST /v1/categories` — Create category (body: `title`); returns 201
- `PUT /v1/categories/{id}` — Update category title
- `DELETE /v1/categories/{id}` — Delete category (fails with 400 if feeds still assigned); returns 204
- `PUT /v1/categories/{id}/mark-all-as-read` — Mark all entries in category as read; returns 204
- `GET /v1/categories/{id}/feeds` — List feeds in a category
- `GET /v1/categories/{id}/entries` — List entries in a category (with filtering)

### 2. Feeds — Subscribe to RSS feeds (7 paths, 10 methods)

- `GET /v1/feeds` — List all feeds for the user
- `GET /v1/feeds/{id}` — Get single feed
- `POST /v1/feeds` — Create/subscribe to a feed (body: `feed_url`, `category_id`, optional `title`, `crawler`, `user_agent`, `disabled`, `scraper_rules`, `rewrite_rules`); returns 201 with `{feed_id: int}`
- `PUT /v1/feeds/{id}` — Update feed properties
- `DELETE /v1/feeds/{id}` — Delete feed (and its entries); returns 204
- `PUT /v1/feeds/{id}/refresh` — Refresh feed (mock — just return 204)
- `PUT /v1/feeds/refresh` — Refresh all feeds (mock — just return 204)
- `GET /v1/feeds/counters` — Get read/unread counters per feed
- `PUT /v1/feeds/{id}/mark-all-as-read` — Mark all entries in feed as read; returns 204
- `GET /v1/feeds/{id}/entries` — List entries for a specific feed (with filtering)

### 3. Entries — Articles from feeds (5 paths, 8 methods)

- `GET /v1/entries` — List all entries for the user (with filtering: status, starred, search, category_id, feed_id, before/after, limit, offset, order, direction)
- `GET /v1/entries/{id}` — Get single entry
- `GET /v1/feeds/{id}/entries/{entry_id}` — Get entry within feed context
- `GET /v1/categories/{id}/entries` — List entries in a category (with filtering)
- `PUT /v1/entries` — Batch update entry status (body: `entry_ids`, `status`); returns 204
- `PUT /v1/entries/{id}` — Update single entry (title, content)
- `PUT /v1/entries/{id}/bookmark` — Toggle bookmark/star status; returns 204
- `POST /v1/feeds/{id}/entries` — **Create entry** (simulates feed fetch; body: `title`, `url`, `content`, `author`, `published_at`); returns 201

Response for list endpoints returns: `{"total": N, "entries": [...]}`

### 4. Users — Multi-user management (4 paths, 7 methods)

- `GET /v1/me` — Get current authenticated user profile
- `GET /v1/users` — List all users (admin only)
- `GET /v1/users/{id}` — Get user by ID (admin only)
- `POST /v1/users` — Create user (admin only; body: `username`, `password`, `is_admin`); returns 201
- `PUT /v1/users/{id}` — Update user (admin only)
- `DELETE /v1/users/{id}` — Delete user (admin only, cannot delete self); returns 204
- `PUT /v1/users/{id}/mark-all-as-read` — Mark all user's entries as read; returns 204

### 5. OPML — Import/Export subscriptions (2 paths, 2 methods)

- `GET /v1/export` — Export all feeds as OPML XML
- `POST /v1/import` — Import OPML XML (creates categories and feeds); returns 201

### 6. Discovery — Find feeds (1 path, 1 method)

- `POST /v1/discover` — Given a website URL, return list of discovered feed URLs (mocked)

### 7. Health & Version (2 paths, 2 methods)

- `GET /healthcheck` — Returns "OK" (no auth required)
- `GET /v1/version` — Returns version string

---

**Totals: ~28 paths, ~45 methods across 7 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all paths/methods** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

## Key Business Rules

1. **Entry status lifecycle**: Entry status is one of `unread`, `read`, or `removed`. New entries default to `unread`. Status changes are tracked.

2. **Starring is independent of read status**: An entry can be starred/bookmarked regardless of whether it's read or unread. Toggling bookmark does not change read status.

3. **Feed-category relationship**: Every feed belongs to exactly one category. A `category_id` is required when creating a feed.

4. **Category deletion rules**: A category cannot be deleted if it still has feeds assigned to it. Return 400 in that case.

5. **Feed deletion cascades**: Deleting a feed removes all its entries.

6. **Mark-all-as-read**: The mark-all-as-read endpoints update all `unread` entries to `read` for the given scope (feed, category, or user). Only entries with status `unread` are affected.

7. **Entry filtering**: The entries list endpoints support filtering by: `status` (unread/read/removed), `starred` (boolean), `search` (text search in title/content), `before`/`after` (entry ID for cursor pagination), `before_timestamp`/`after_timestamp` (Unix timestamps), `category_id`, `feed_id`, `limit`, `offset`, `order` (id/published_at/created_at/status/category_title), `direction` (asc/desc).

8. **Feed counters**: `GET /v1/feeds/counters` returns `{"reads": {"<feed_id>": count, ...}, "unreads": {"<feed_id>": count, ...}}` for all user's feeds. Feed IDs are string keys in the maps.

9. **OPML import**: Parsing OPML XML creates categories (from outline groups) and feeds (from outline items with xmlUrl). If a category already exists (by title), reuse it. If a feed with the same URL already exists, skip it.

10. **OPML export**: Returns valid OPML 2.0 XML with feeds grouped by category.

11. **User management**: Only admin users can create/list/delete other users. Any user can view their own profile via `/v1/me`. Admin cannot delete themselves.

12. **Feed discovery (mocked)**: `POST /v1/discover` with `{"url": "..."}` returns a list with one entry: `[{"url": "<the_url>", "title": "Discovered Feed"}]`. This simulates feed auto-discovery.

13. **Default ordering**: Entries are returned ordered by `published_at DESC` by default (newest first).

14. **Entry uniqueness**: Within a feed, entries are unique by URL. Creating an entry with a duplicate URL within the same feed should be ignored (return the existing entry, not an error).

15. **Cannot delete self**: An admin cannot delete their own user account. Return `400 Bad Request`.

16. **Unique category titles per user**: A user cannot have two categories with the same title. Return `409 Conflict` on duplicate.

17. **Unique feed URLs per user**: A user cannot subscribe to the same `feed_url` twice. Return `409 Conflict` on duplicate.

18. **Admin protection**: Only admin users can access user management endpoints (`/v1/users`, `/v1/users/{id}`). Non-admin users receive `403 Forbidden`. The `GET /v1/me` endpoint is accessible to all authenticated users.

19. **User cascade delete**: Deleting a user deletes all their categories, feeds, entries.
