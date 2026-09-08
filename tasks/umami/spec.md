# Umami — Backend Implementation Spec

## Overview

Umami is a **privacy-focused web analytics platform** (based on [Umami](https://github.com/umami-software/umami), 36.4K stars). Users register websites to track, collect pageview and custom event data via a public tracking endpoint, and query aggregated statistics — top pages, referrers, browsers, time-series pageviews, bounce rates, and realtime visitor counts.

The core challenge is correct session detection, bounce rate calculation, and time-series aggregation.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-Api-Key`: API key identifying the user

Rules:
- The `X-Api-Key` header is required on all endpoints **except** `GET /api/health`, `POST /api/collect`, and `GET /api/share/{shareId}`.
- If the header is missing on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — the key IS the username. If a user with that name doesn't exist, **auto-create** the user. The first user auto-created becomes admin.
- **Data scoping**: Websites are owned by the user who created them. Users can only see/modify their own websites. Team members can view analytics for shared websites.
- **Admin endpoints**: User management (`GET /api/users`, `GET /api/users/{userId}`, `PUT /api/users/{userId}`, `DELETE /api/users/{userId}`) requires admin privileges. Non-admin users get `403 Forbidden`.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (32 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Health (1 endpoint)

- `GET /api/health` — Returns health status (no auth required)

### 2. Current User (1 endpoint)

- `GET /api/me` — Get the currently authenticated user

### 3. Users — admin only (4 endpoints)

- `GET /api/users` — List all users (admin only)
- `GET /api/users/{userId}` — Get user by ID (admin only)
- `PUT /api/users/{userId}` — Update user (admin only)
- `DELETE /api/users/{userId}` — Delete user and cascade (admin only)

### 4. Websites (6 endpoints)

- `GET /api/websites` — List websites owned by current user
- `POST /api/websites` — Create a website
- `GET /api/websites/{websiteId}` — Get a website by ID
- `PUT /api/websites/{websiteId}` — Update a website
- `DELETE /api/websites/{websiteId}` — Delete a website (cascades all events/sessions)
- `POST /api/websites/{websiteId}/reset` — Reset all analytics data for a website

### 5. Event Collection (1 endpoint)

- `POST /api/collect` — Record a pageview or custom event (NO auth — public tracking endpoint)

### 6. Sessions (2 endpoints)

- `GET /api/websites/{websiteId}/sessions` — List sessions for a website
- `GET /api/websites/{websiteId}/sessions/{sessionId}` — Get session detail with its events

### 7. Stats (1 endpoint)

- `GET /api/websites/{websiteId}/stats` — Aggregated statistics (pageviews, visitors, visits, bounceRate, totaltime)

### 8. Metrics (1 endpoint)

- `GET /api/websites/{websiteId}/metrics` — Breakdown by dimension (url, referrer, browser, os, device, country, event)

### 9. Pageviews (1 endpoint)

- `GET /api/websites/{websiteId}/pageviews` — Time-series pageview + session data

### 10. Events (1 endpoint)

- `GET /api/websites/{websiteId}/events` — Custom event summary (name + count)

### 11. Realtime (1 endpoint)

- `GET /api/websites/{websiteId}/active` — Active visitors in last 5 minutes

### 12. Teams (5 endpoints)

- `GET /api/teams` — List teams the current user belongs to
- `POST /api/teams` — Create a team
- `GET /api/teams/{teamId}` — Get team details
- `PUT /api/teams/{teamId}` — Update team name
- `DELETE /api/teams/{teamId}` — Delete team (owner only)

### 13. Team Members (3 endpoints)

- `GET /api/teams/{teamId}/members` — List team members
- `POST /api/teams/{teamId}/members` — Add a member to team
- `DELETE /api/teams/{teamId}/members/{userId}` — Remove a member

### 14. Team Websites (3 endpoints)

- `GET /api/teams/{teamId}/websites` — List websites shared with team
- `POST /api/teams/{teamId}/websites` — Share a website with team
- `DELETE /api/teams/{teamId}/websites/{websiteId}` — Unshare a website

### 15. Public Share (1 endpoint)

- `GET /api/share/{shareId}` — Get public website stats by share ID (no auth required)

---

**Totals: 32 endpoints across 15 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 32 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

### Session Detection

1. **Fingerprint**: A session fingerprint is computed as `SHA256(websiteId + ip + userAgent)` (hex digest, lowercase). The `ip` and `userAgent` fields come from the collect request body. This fingerprint identifies a unique visitor.

2. **Session continuity**: When an event arrives via `POST /api/collect`, find an existing session for the same fingerprint AND websiteId where `lastActivityAt` was within 30 minutes. If found, reuse that session (update its `lastActivityAt`). If not found (or gap > 30 min), create a new session.

3. **Session metadata**: `browser`, `os`, `device`, and `country` are stored on the session (from the first event that created it). They do not change on subsequent events.

### Event Collection

4. **Event types**: Events are either `pageview` (when `eventName` is null/empty in the payload) or `custom` (when `eventName` is provided with a non-empty value).

5. **No auth on collect**: The `/api/collect` endpoint requires no authentication. It identifies the website by `websiteId` in the request body. If the websiteId is invalid (no such website), return `400`.

6. **Required fields**: `websiteId`, `url`, `ip`, and `userAgent` are required in the collect payload. `referrer`, `browser`, `os`, `device`, `country`, `eventName`, `eventData` are optional.

### Stats Aggregation

7. **Pageviews**: Total count of events where eventType = 'pageview' in the time range.

8. **Visitors**: Count of distinct session fingerprints that have at least one event in the time range.

9. **Visits**: Count of distinct sessions (by session ID) that have at least one event in the time range.

10. **Bounce rate**: Number of sessions that have exactly 1 pageview event / total sessions that have at least 1 pageview event, in the time range. Returned as a decimal (0.0 to 1.0). If no sessions have pageviews, return 0.

11. **Total time**: Sum of (lastActivityAt - createdAt) in seconds for all sessions that have at least one event in the time range. Sessions with only 1 event contribute 0 seconds. Returned as integer (rounded down).

### Metrics

12. **Type parameter**: The `type` query parameter specifies the dimension: `url`, `referrer`, `browser`, `os`, `device`, `country`, `event`.

13. **Response**: Array of `{name, count}` objects sorted by count descending, then by name ascending.

14. **URL metrics**: For type=url, `name` is the URL from pageview events.

15. **Event metrics**: For type=event, `name` is the eventName from custom events.

16. **Other metrics** (browser, os, device, country, referrer): Counted per unique session (not per event). Each session contributes at most 1 to each dimension value.

### Pageviews Time Series

17. **Unit parameter**: `hour`, `day`, or `month`. Groups events by the specified time unit.

18. **Response**: Object with `pageviews` and `sessions` arrays. Each entry has `date` (start of time bucket) and `count`. Date format: `YYYY-MM-DDTHH:00:00` for hour, `YYYY-MM-DD` for day, `YYYY-MM-01` for month.

19. **Pageviews array**: Counts pageview events in each bucket.

20. **Sessions array**: Counts distinct sessions (by session ID) that had at least one event in each bucket.

### Realtime

21. **Active visitors**: Count of distinct session fingerprints with `lastActivityAt` within the last 5 minutes from current server time.

### Date Filtering

22. **All analytics endpoints** (stats, metrics, pageviews, events, sessions, active) accept `startAt` and `endAt` query parameters as Unix timestamps in milliseconds. Both are required.

### Ownership & Access

23. **Website ownership**: Only the user who created a website can update/delete/reset it. Accessing another user's website (that's not shared via team) returns `404`.

24. **Team access**: Team members can view analytics (stats, metrics, pageviews, events, sessions, active) for websites shared with their team. They cannot modify or delete the website.

25. **Admin privileges**: Admin users can list/view/update/delete all users. Non-admin users get `403` on user management endpoints.

26. **Cannot delete self**: An admin cannot delete their own user account. Return `400`.

### Teams

27. **Team ownership**: The user who creates a team is the owner. Only the owner can delete the team or manage members/websites.

28. **Member management**: Only team owners can add/remove members and add/remove websites. Adding a member requires providing a valid userId. Cannot add the same user twice (return `409`).

29. **Team deletion cascade**: Deleting a team removes all team-member and team-website associations.

### Websites

30. **Share ID**: A website can have a `shareId` (unique string) for public access. If set, anyone can view stats via `GET /api/share/{shareId}` without auth. If null/empty, the website is not publicly shared.

31. **Reset**: `POST /api/websites/{websiteId}/reset` deletes all events and sessions for that website but keeps the website itself.

32. **Delete cascade**: Deleting a website deletes all its sessions, events, and removes it from any teams.

### Public Share

33. **Share endpoint**: `GET /api/share/{shareId}` returns the same stats structure as `GET /api/websites/{websiteId}/stats`. Requires `startAt` and `endAt` query params. Returns `404` if shareId not found.
