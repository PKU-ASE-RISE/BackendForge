# Shlink — Backend Implementation Spec

## Overview

Shlink is a **self-hosted URL shortener** (based on [Shlink](https://github.com/shlinkio/shlink), 4.9K stars). Users create short URLs with custom or auto-generated slugs, track visits (who clicked, when, from where), organize URLs with tags, and manage multiple domains.

The application is deployed for personal or organizational link management. A typical deployment handles thousands of short URLs with millions of redirect visits.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based API key authentication:
- `X-Api-Key`: API key identifying the caller

Rules:
- The `X-Api-Key` header is required on all endpoints **except** `GET /rest/health` and `GET /{shortCode}` (redirect).
- If the header is missing or empty on a protected endpoint, return `401 Unauthorized` with body: `{"type": "INVALID_API_KEY", "detail": "Expected one of the following authentication headers, but none were provided", "title": "Invalid API key", "status": 401}`
- Trust header values directly — any non-empty value is accepted as valid. No database lookup required.
- There is no multi-user isolation — all API keys see the same data (single-tenant).

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (17 paths, 28 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Short URLs — core CRUD (4 paths, 7 methods)

Create, list, update, and delete short URLs with optional custom slugs, tags, visit limits, and date ranges.

- `GET /rest/v3/short-urls` — Paginated list with filtering (searchTerm, tags, startDate, endDate, orderBy)
- `POST /rest/v3/short-urls` — Create a short URL (body: `longUrl` required; optional `customSlug`, `tags`, `maxVisits`, `validSince`, `validUntil`, `title`, `crawlable`, `domain`, `findIfExists`)
- `GET /rest/v3/short-urls/{shortCode}` — Get single short URL details (query: optional `domain`)
- `PATCH /rest/v3/short-urls/{shortCode}` — Update a short URL (body: partial update fields; query: optional `domain`)
- `DELETE /rest/v3/short-urls/{shortCode}` — Delete a short URL (query: optional `domain`)
- `GET /rest/v3/short-urls/{shortCode}/visits` — List visits for a short URL (paginated)

### 2. Redirect — the core function (1 path, 1 method)

- `GET /{shortCode}` — Redirect to the long URL and record a visit. No auth required. Returns 302 redirect. Returns 404 if short code not found, max visits exceeded, or outside valid date range.

### 3. Visits — analytics (4 paths, 4 methods)

Global and per-entity visit listing with pagination.

- `GET /rest/v3/visits` — Global visit stats (summary counts)
- `GET /rest/v3/visits/non-orphan` — List all non-orphan visits (paginated)
- `GET /rest/v3/visits/orphan` — List orphan visits (paginated)
- `GET /rest/v3/short-urls/{shortCode}/visits` — List visits for a specific short URL (paginated)

### 4. Tags — organize short URLs (3 paths, 5 methods)

- `GET /rest/v3/tags` — List all tags with optional stats
- `POST /rest/v3/tags` — Create tags (body: `tags` array of strings)
- `PUT /rest/v3/tags` — Rename a tag (body: `oldName`, `newName`)
- `DELETE /rest/v3/tags` — Delete tags (query: `tags[]` array)
- `GET /rest/v3/tags/{tag}/visits` — Visits for URLs with this tag (paginated)

### 5. Domains — multi-domain support (3 paths, 3 methods)

- `GET /rest/v3/domains` — List all domains
- `PATCH /rest/v3/domains/redirects` — Configure redirects for a domain
- `GET /rest/v3/domains/{domain}/visits` — List visits for all short URLs under a domain (paginated)

### 6. Health — system status (1 path, 1 method)

- `GET /rest/health` — Returns health status (no auth required)

---

**Totals: 17 paths, 28 endpoints across 6 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all paths/methods** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Short code generation**: If no `customSlug` is provided, auto-generate a random alphanumeric slug of 5-8 characters (lowercase letters and digits only). Custom slugs must match `^[a-zA-Z0-9-]+$` (alphanumeric + dashes); reject invalid slugs with 400 and type `INVALID_SLUG`.

2. **Short code uniqueness**: Short codes must be unique within a domain. If `customSlug` conflicts with an existing code on the same domain, return 400 with type `INVALID_SLUG`.

3. **Max visits enforcement**: When a short URL has `maxVisits` set and the visit count reaches that limit, subsequent redirect requests (`GET /{shortCode}`) return 404. The short URL still exists and is visible via the API — it just doesn't redirect anymore.

4. **Valid date range enforcement**: If `validSince` is set and the current time is before it, redirect returns 404. If `validUntil` is set and the current time is after it, redirect returns 404. The short URL is still visible via the API.

5. **Visit recording**: Each successful redirect (302) increments the visit count and creates a visit record with: `referer` (from Referer header), `userAgent` (from User-Agent header), `date` (ISO-8601 timestamp), `visitedUrl` (the short URL path that was accessed), and `potentialBot` (true if user-agent contains "bot", "crawl", "spider", "slurp" case-insensitive, false otherwise).

6. **Tags deduplication**: Tags are global. When creating/updating short URLs with tags, reuse existing tag entities by name (case-insensitive matching). Tag names are stored as provided on first creation.

7. **Tag stats**: Each tag tracks `shortUrlsCount` (number of short URLs using it) and `visitsCount` (total visits across all short URLs using it). These are computed dynamically.

8. **Find if exists**: When creating with `findIfExists: true`, if a short URL with the same `longUrl` already exists (same domain), return the existing one (200) instead of creating a duplicate.

9. **Domain handling**: Short URLs belong to a domain. The "default" domain is used when no domain is specified (stored as null internally). When querying by shortCode, an optional `domain` query parameter can narrow the lookup. The default domain is represented as `"DEFAULT"` in the domains list with `isDefault: true`.

10. **Pagination**: List endpoints use `page` (default 1) and `itemsPerPage` (default 10) query params. Response wraps data in type-specific key: `shortUrls`, `visits`, or `tags`. Each contains `data` (array) and `pagination` object with: `currentPage`, `pagesCount`, `itemsPerPage`, `itemsInCurrentPage`, `totalItems`.

11. **Tag visits**: `GET /rest/v3/tags/{tag}/visits` returns visits across ALL short URLs that have the specified tag.

12. **Crawlable flag**: The `crawlable` field on a short URL defaults to `false`. This is metadata only (does not affect redirect behavior).

13. **Delete short URL**: Deleting a short URL also deletes all its visit records.

14. **Rename tag**: Renaming a tag updates the tag name. If `oldName` doesn't exist, return 404 with type `TAG_NOT_FOUND`. If `newName` already exists, return 409 with type `TAG_CONFLICT`.

15. **Domain redirects**: Each domain can have configured redirects: `baseUrlRedirect`, `regular404Redirect`, `invalidShortUrlRedirect`. These are stored as configuration and returned in the domains list.

16. **OrderBy for short URLs**: The `orderBy` query parameter accepts values like `dateCreated-ASC`, `dateCreated-DESC`, `shortCode-ASC`, `shortCode-DESC`, `longUrl-ASC`, `longUrl-DESC`, `visits-ASC`, `visits-DESC`. Default ordering is by `dateCreated-DESC`.

17. **Orphan visits**: When a request hits `GET /{shortCode}` but the short code doesn't exist, record an orphan visit with `type: "invalid_short_url"`. Orphan visits are listed separately via `GET /rest/v3/visits/orphan`.

18. **Visit summary on short URL**: Each short URL in responses includes a `visitsSummary` object with `total` (all visits), `nonBots` (visits where potentialBot is false), `bots` (visits where potentialBot is true).

19. **Short URL dateCreated**: Automatically set to the current ISO-8601 timestamp when the short URL is created. Cannot be modified.
