# Ntfy — Backend Implementation Spec

## Overview

Ntfy is a **self-hosted push notification service** (based on [ntfy](https://github.com/binwiederhier/ntfy), 29.9K★). It provides pub/sub notifications via topics — users publish messages to topics, and subscribers receive them. Supports priority levels, tags, scheduled delivery, message actions, and per-topic access control.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)

## Authentication

Header-based auth (no JWT/OAuth):
- `X-User-Id`: String identifier of the current user
- `X-Token`: Token string for the current user

Rules:
- Both headers are required on every authenticated request. If either is missing, return `401 Unauthorized`.
- Trust header values directly — no database lookup to verify credentials is required.
- If the user identified by `X-User-Id` does not exist in the database, auto-create the user record on the first request. The first user ever created is automatically an admin.
- **Data scoping**: Messages belong to topics. Subscriptions, tokens, and rate-limit tracking belong to individual users.
- Admin endpoints require the user's `admin` flag to be `true`; non-admin users receive `403 Forbidden`.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (37 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Health (1 endpoint)

- `GET /api/health` — Health check (no auth required). Returns `{"status": "ok"}`.

### 2. Users — admin CRUD (5 endpoints)

Admin-only user management. Users are auto-created on first authenticated request, but admins can also create/manage them explicitly.

- `POST /api/users` — Create user (admin only). Body: `{username, admin}`.
- `GET /api/users` — List all users (admin only).
- `GET /api/users/{userId}` — Get user by ID (admin only).
- `PUT /api/users/{userId}` — Update user (admin only). Body: `{username, admin, tier}`.
- `DELETE /api/users/{userId}` — Delete user (admin only). Cannot delete self.

### 3. Tokens — API token management (4 endpoints)

Users manage their own API tokens. Tokens are string identifiers with optional labels and expiry metadata.

- `POST /api/tokens` — Create a token for the current user. Body: `{label, expires}`.
- `GET /api/tokens` — List all tokens for the current user.
- `PATCH /api/tokens/{tokenId}` — Update token metadata (label, expires).
- `DELETE /api/tokens/{tokenId}` — Revoke (delete) a token.

### 4. Topics — pub/sub channels (5 endpoints)

Topics are named channels for notifications. Publishing to a non-existent topic auto-creates it.

- `POST /api/topics` — Explicitly create a topic. Body: `{name, description}`.
- `GET /api/topics` — List all topics (optionally filtered by subscription).
- `GET /api/topics/{topic}` — Get topic details by name.
- `PUT /api/topics/{topic}` — Update topic metadata (admin only). Body: `{description}`.
- `DELETE /api/topics/{topic}` — Delete topic and all its messages (admin only).

### 5. Messages — publish & retrieve (6 endpoints)

Messages are published to topics and stored for retrieval. Support priority, tags, title, actions, attachment metadata, and scheduled delivery.

- `POST /api/topics/{topic}/messages` — Publish a message to a topic. Body: `{message, title, priority, tags, actions, attachment, scheduledAt}`.
- `GET /api/topics/{topic}/messages` — List messages for a topic. Supports filters: `since`, `priority`, `tags`, `title`, `scheduled`.
- `GET /api/topics/{topic}/messages/scheduled` — List scheduled (undelivered) messages for a topic.
- `GET /api/messages/{messageId}` — Get a single message by ID.
- `DELETE /api/messages/{messageId}` — Delete a message (admin or message publisher).
- `DELETE /api/messages/{messageId}/schedule` — Cancel a scheduled message before delivery.

### 6. Subscriptions — user topic subscriptions (5 endpoints)

Users subscribe to topics to track which topics they follow. Subscriptions can have filters.

- `POST /api/subscriptions` — Subscribe to a topic. Body: `{topic, filterPriority, filterTags, filterTitle}`.
- `GET /api/subscriptions` — List current user's subscriptions.
- `GET /api/subscriptions/{subscriptionId}` — Get subscription details.
- `PUT /api/subscriptions/{subscriptionId}` — Update subscription filters.
- `DELETE /api/subscriptions/{subscriptionId}` — Unsubscribe.

### 7. Access Control — per-topic permissions (3 endpoints)

Admin-managed per-topic per-user read/write permissions. Default access is open (everyone can read/write).

- `PUT /api/topics/{topic}/access` — Set access rule for a user on a topic (admin only). Body: `{userId, read, write}`.
- `GET /api/topics/{topic}/access` — List access rules for a topic (admin only).
- `DELETE /api/topics/{topic}/access/{userId}` — Remove user-specific access rule (admin only), reverting to default.

### 8. Stats (2 endpoints)

- `GET /api/topics/{topic}/stats` — Get topic statistics (message count, subscriber count).
- `GET /api/stats` — Get global stats: total topics, total messages, total users (admin only).

### 9. Tiers — rate limiting configuration (4 endpoints)

Tiers define rate limits for users. Each user can be assigned a tier.

- `POST /api/tiers` — Create a tier (admin only). Body: `{name, messagesPerDay, messagesPerMinute}`.
- `GET /api/tiers` — List all tiers.
- `PUT /api/tiers/{tierId}` — Update tier (admin only).
- `DELETE /api/tiers/{tierId}` — Delete tier (admin only). Cannot delete if users are assigned.

### 10. Admin Operations (2 endpoints)

- `POST /api/admin/prune` — Prune messages older than specified retention. Body: `{olderThanSeconds}`. Returns count of pruned messages.
- `POST /api/admin/rate-reset` — Reset rate limit counters for a user (admin only). Body: `{userId}`.

---

**Totals: 37 endpoints across 10 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 37 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Topic auto-creation**: Publishing a message to a non-existent topic auto-creates that topic. The topic name comes from the URL path parameter.

2. **Priority levels**: Messages have priority 1 (min) to 5 (max), default 3. Invalid priority values outside this range should be clamped (1 if below, 5 if above).

3. **Scheduled messages**: If `scheduledAt` is provided (ISO 8601 timestamp in the future), the message is stored but not considered "delivered" until that time passes. Scheduled messages appear in the `/scheduled` endpoint but NOT in the regular message list until their scheduled time has passed. Messages with `scheduledAt` in the past are treated as immediate.

4. **Cancel scheduled**: Only messages that haven't been delivered yet (scheduledAt is in the future) can be cancelled via `DELETE /api/messages/{id}/schedule`. Cancelling removes the message entirely.

5. **Message retention / prune**: The admin prune endpoint deletes messages older than the specified seconds. Only delivered (non-scheduled-future) messages are pruned.

6. **Access control defaults**: By default, all topics are open — any authenticated user can read and write. When an explicit access rule is added for a topic, ONLY users with explicit rules can access that topic (the topic becomes "restricted"). Removing all access rules for a topic reverts it to open.

7. **Access enforcement**:
   - Publishing requires write access to the topic.
   - Reading messages requires read access to the topic.
   - If a user lacks the required access, return `403 Forbidden`.
   - Admins always have full access regardless of access rules.

8. **Rate limiting**: When a tier is assigned to a user, track message publish counts. If the user exceeds `messagesPerMinute` or `messagesPerDay`, return `429 Too Many Requests`. Users without a tier have no rate limit.

9. **Tags**: Tags are provided as a comma-separated string in the publish request, stored as a JSON array internally, and returned as an array in responses.

10. **Message actions**: The `actions` field stores action metadata (array of objects with `action`, `label`, `url` fields). This is stored as-is (no server-side execution). Action types: "view" (opens URL), "broadcast" (sends broadcast), "http" (makes HTTP request) — all stored as metadata only.

11. **Attachment metadata**: The `attachment` field stores file reference metadata (`{name, url, type, size}`). No actual file upload — just metadata storage.

12. **Subscription filters**: When a subscription has filters set (filterPriority, filterTags, filterTitle), these are stored metadata only — they don't affect what the GET messages endpoint returns (filtering is client-side concern). The filters are informational.

13. **First user is admin**: The very first user record created in the system (whether by auto-creation or explicit creation) gets `admin: true`. All subsequent users get `admin: false` by default.

14. **Duplicate handling**: Creating a subscription to a topic the user is already subscribed to returns `409 Conflict`. Creating a topic with a name that already exists returns `409 Conflict`. Creating a user with a username that already exists returns `409 Conflict`.

15. **Cascade deletes**: Deleting a topic deletes all its messages, subscriptions, and access rules. Deleting a user deletes their tokens, subscriptions, and any messages they published.
