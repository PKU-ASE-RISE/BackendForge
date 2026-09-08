# Memos — Backend Implementation Spec

## Overview

Memos is a **privacy-first, lightweight note-taking hub** (based on [Memos](https://github.com/usememos/memos), 59K stars). Think of it as a self-hosted Twitter/Flomo for personal thoughts. Users create short notes (memos) in Markdown, tag them with `#hashtags`, attach resource metadata, react to each other's memos, and link memos together.

The application is self-hosted, multi-user, with role-based access (HOST/USER) and visibility controls (PUBLIC/PROTECTED/PRIVATE).

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (SQLite, PostgreSQL, in-memory, etc.)

## Authentication

Header-based auth (no JWT/OAuth):
- `X-User-Id`: UUID of the current user

Rules:
- The header is required on every request. If missing, return `401 Unauthorized`.
- Trust header values directly — no database lookup to verify the user exists is required for authentication purposes. However, the user **must exist** in the database for write operations (creating memos, etc.). If a user with the given ID does not exist, return `401 Unauthorized`.
- Exception: `POST /api/users` (user creation) does NOT require `X-User-Id` header when creating the first user (HOST). Subsequent user creation requires the caller to be HOST.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (23 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Users — registration and profile (4 endpoints)

Multi-user with two roles: HOST (admin) and USER (regular).

- `POST /api/users` — Create user (first user becomes HOST automatically; subsequent creation requires HOST role)
- `GET /api/users` — List all users (authenticated)
- `GET /api/users/{id}` — Get user by ID
- `PATCH /api/users/{id}` — Update user profile (users can only update their own profile; HOST can update anyone)

### 2. Memos — core CRUD + search + filter (5 endpoints)

Short notes with Markdown content, visibility control, and pinned status.

- `POST /api/memos` — Create memo (content, visibility, pinned)
- `GET /api/memos` — List memos (paginated, filterable by visibility, tag, pinned, creatorId, search, date range)
- `GET /api/memos/{id}` — Get single memo
- `PATCH /api/memos/{id}` — Update memo (only owner can update)
- `DELETE /api/memos/{id}` — Delete memo (only owner or HOST can delete)

### 3. Tags — auto-extracted from memo content (3 endpoints)

Tags are automatically extracted from memo content using `#tag` syntax. They are per-user (each user has their own tag namespace).

- `GET /api/tags` — List all tags for the authenticated user (with memo count per tag)
- `DELETE /api/tags/{tag}` — Delete a tag (removes it from all of the user's memos by rewriting content)
- `POST /api/tags/rename` — Rename a tag across all user's memos

### 4. Resources — attachment metadata (5 endpoints)

Resources represent file/image metadata linked to memos. No actual file upload — just metadata CRUD.

- `POST /api/resources` — Create resource metadata
- `GET /api/resources` — List resources for authenticated user
- `GET /api/resources/{id}` — Get single resource
- `PATCH /api/resources/{id}` — Update resource metadata (only owner)
- `DELETE /api/resources/{id}` — Delete resource (only owner)

### 5. Memo Reactions (3 endpoints)

Users can react to memos with emoji reactions.

- `POST /api/memos/{memoId}/reactions` — Add reaction to a memo
- `GET /api/memos/{memoId}/reactions` — List reactions on a memo
- `DELETE /api/reactions/{id}` — Delete a reaction (only the reactor can delete)

### 6. Memo Relations (3 endpoints)

Memos can reference other memos, creating a directional link.

- `POST /api/memos/{memoId}/relations` — Create a relation (REFERENCE type)
- `GET /api/memos/{memoId}/relations` — List relations for a memo
- `DELETE /api/memos/{memoId}/relations/{relatedMemoId}` — Delete a relation

---

**Totals: 23 endpoints across 6 groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 23 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes)
3. **Starts empty** — no seed data on startup

## Key Business Rules (not obvious from the API spec alone)

1. **Tag auto-extraction**: When a memo is created or updated, tags are automatically extracted from the content by parsing `#tag` patterns. A tag is a `#` followed by one or more word characters (letters, digits, underscores) or hyphens. Examples: `#work`, `#project-x`, `#2024`. Tags in code blocks should still be extracted for simplicity.

2. **Tag list with counts**: `GET /api/tags` returns all unique tags for the authenticated user with a count of how many memos contain each tag. Only counts memos owned by the user.

3. **Tag deletion**: `DELETE /api/tags/{tag}` removes the `#tag` text from all of the user's memos content. If a memo's only content was the tag, the content becomes empty string.

4. **Tag rename**: `POST /api/tags/rename` with body `{"oldName": "...", "newName": "..."}` replaces `#oldName` with `#newName` in all of the user's memos content.

5. **Pinned ordering**: When listing memos, pinned memos always appear before unpinned memos. Within each group (pinned/unpinned), memos are ordered by `createdAt` descending (newest first).

6. **Visibility rules**:
   - `PRIVATE`: Only visible to the owner
   - `PROTECTED`: Visible to any authenticated user
   - `PUBLIC`: Visible to any authenticated user
   - When listing memos without a `creatorId` filter: returns the user's own memos (all visibilities) PLUS other users' PUBLIC and PROTECTED memos
   - When listing with `creatorId` filter for another user: returns only that user's PUBLIC and PROTECTED memos
   - Get single memo by ID: same rules apply (404 if not visible)

7. **First user is HOST**: The first user created (via `POST /api/users`) automatically gets the `HOST` role regardless of what role is specified in the request. All subsequent users get the `USER` role.

8. **HOST privileges**: HOST can update any user's profile, delete any memo, and create new users. Regular USERs can only manage their own data.

9. **Reactions uniqueness**: A user can have multiple reactions on the same memo, but cannot have duplicate reaction types. If a user tries to add a reaction with the same `reactionType` to the same memo, return `409 Conflict`.

10. **Memo relations**: Relations are directional — memo A references memo B. A memo cannot reference itself. Creating a duplicate relation (same memoId -> same relatedMemoId with same type) returns `409 Conflict`.

11. **Resource ownership**: Resources belong to the user who created them. A resource can optionally be linked to a memo via `memoId`. Only the owner can view/update/delete their resources. Non-owners get 404 (not 403) when trying to access another user's resource (to not leak existence).

12. **Search**: The `search` query parameter on `GET /api/memos` performs case-insensitive substring matching on memo `content`.

13. **Date filtering**: `GET /api/memos` supports `createdAfter` and `createdBefore` query parameters (ISO 8601 format) to filter memos by creation date.

14. **Pagination**: `GET /api/memos` uses `limit` and `offset` query parameters. Default limit is 20, max is 100. Response includes `total` count for the filtered result set.
