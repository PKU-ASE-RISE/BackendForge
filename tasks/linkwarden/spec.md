# Linkwarden — Backend Implementation Spec

## Overview

Linkwarden is a **self-hosted collaborative bookmark manager** (based on [Linkwarden](https://github.com/linkwarden/linkwarden), 18K★). Users collect, organize, and share web links in collections with hierarchical organization, tag-based categorization, text highlights, and role-based access control for team collaboration.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (SQLite recommended for simplicity)

## Authentication

Header-based auth (no JWT/OAuth):
- `X-User-Id`: UUID of the current user

Rules:
- The header is required on every authenticated request. If missing, return `401 Unauthorized`.
- Trust the header value directly — no database lookup to verify the user exists.
- The user record is auto-created on first use (first time a request is made with that user ID, create a user record and a default "Unorganized" collection for them).
- **Data scoping**: Each user owns their own links, collections, and tags. Cross-user access is only possible through collection membership (sharing).

**Exception**: Public endpoints (`/api/public/*`) do NOT require authentication headers.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (30 paths, ~38 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Links — CRUD + Search (3 paths, 6 methods)

Bookmarks with URL, title, description, collection assignment, and tags.

- `GET /api/links` — List links for the authenticated user (includes shared collections). Supports `search`, `collectionId`, `tagId` query params. Returns paginated array.
- `POST /api/links` — Create a new link (body: `url` required, `name`, `description`, `collectionId`, `tags`). If no `collectionId`, assign to user's "Unorganized" collection.
- `GET /api/links/{id}` — Get a single link by ID. Must be owner or member of the link's collection.
- `PUT /api/links/{id}` — Update a link. Permission: owner, or admin/contributor (contributor only own links).
- `DELETE /api/links/{id}` — Delete a link. Permission: owner, or admin/contributor (contributor only own links).
- `POST /api/links/bulk` — Bulk import links. Body: array of `{url, name, collectionId, tags}`. Returns created links.

### 2. Collections — CRUD + Hierarchy (3 paths, 5 methods)

Folders/groups for organizing links. Support nesting via `parentId`.

- `GET /api/collections` — List all collections the user owns or is a member of.
- `POST /api/collections` — Create a collection (body: `name` required, `description`, `color`, `parentId`, `isPublic`).
- `GET /api/collections/{id}` — Get a single collection. Must be owner or member.
- `PUT /api/collections/{id}` — Update a collection. Only owner or admin can update.
- `DELETE /api/collections/{id}` — Delete a collection. Only owner can delete. Query param `deleteChildren=true` deletes child collections recursively; otherwise children move to root (parentId=null).

### 3. Tags — CRUD (2 paths, 4 methods)

Labels for categorizing links. Scoped per-user but shared across a user's collections.

- `GET /api/tags` — List all tags for the authenticated user.
- `POST /api/tags` — Create a tag (body: `name` required).
- `PUT /api/tags/{id}` — Update a tag name.
- `DELETE /api/tags/{id}` — Delete a tag. Removes tag association from all links.

### 4. Members — Collection Sharing (2 paths, 4 methods)

Invite other users to collaborate on a collection with role-based permissions.

- `GET /api/collections/{id}/members` — List members of a collection. Only owner/admin can view.
- `POST /api/collections/{id}/members` — Add a member (body: `userId`, `role`). Only owner/admin can add.
- `PUT /api/collections/{id}/members/{memberId}` — Update member role. Only owner can change roles.
- `DELETE /api/collections/{id}/members/{memberId}` — Remove a member. Owner can remove anyone; admin can remove contributors/viewers; members can remove themselves.

### 5. Highlights — Link Annotations (2 paths, 4 methods)

Text highlights/annotations saved from a link's content.

- `GET /api/links/{linkId}/highlights` — List highlights for a link.
- `POST /api/links/{linkId}/highlights` — Create a highlight (body: `text` required, `color`, `note`).
- `PUT /api/highlights/{id}` — Update a highlight.
- `DELETE /api/highlights/{id}` — Delete a highlight.

### 6. Public Access (2 paths, 2 methods)

Unauthenticated access to public collections and their links.

- `GET /api/public/collections/{id}` — Get a public collection's details. Returns 404 if not public.
- `GET /api/public/collections/{id}/links` — Get links in a public collection. Returns 404 if not public.

### 7. Search (1 path, 1 method)

Full-text search across links.

- `GET /api/search` — Search links by query string. Searches across `name`, `url`, `description`, and tag names. Supports `collectionId` and `tagId` filters.

### 8. Dashboard (1 path, 1 method)

Aggregate statistics.

- `GET /api/dashboard` — Returns `totalLinks`, `totalCollections`, `totalTags`, `linksPerDay` (array of `{date, count}` for last 7 days).

### 9. Export (1 path, 1 method)

Data export.

- `GET /api/export` — Export all user's links as JSON array.

---

**Totals: 17 paths, 28 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 17 paths / 28 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup (each user's "Unorganized" collection is created on-demand)

## Key Business Rules

1. **Default "Unorganized" collection**: Every user gets an auto-created "Unorganized" collection on their first request. All links without an explicit `collectionId` go here. This collection cannot be deleted.

2. **Collection hierarchy**: Collections can nest via `parentId`. Deleting a parent with `deleteChildren=true` recursively deletes all descendants and their links. Without the flag (or `deleteChildren=false`), child collections move to root (`parentId` becomes null). When a collection is deleted, any links inside it are moved to the user's "Unorganized" collection (not deleted).

3. **Permission cascade**: If a user is a member of a parent collection, they have the same role on all its child collections (recursively). You don't need to store separate membership records for children — just check up the parent chain.

4. **Member roles**:
   - **owner**: Full control (only the creator). Cannot be removed.
   - **admin**: Can manage members (add/remove contributor/viewer), edit/delete any link in the collection.
   - **contributor**: Can add links, edit/delete only their own links.
   - **viewer**: Read-only access to links in the collection.

5. **Tag deduplication**: Tags are unique per user (case-insensitive). Creating a link with `tags: [{name: "Existing-Tag"}]` reuses the existing tag (matched case-insensitively). POST /api/tags with a duplicate name returns the existing tag (200), not a 409.

6. **Link ownership**: Every link has a `createdBy` field (the user who created it). A link belongs to exactly one collection. Moving a link to a different collection (via PUT) is allowed if the user has write access to both the source and destination collections.

7. **Public collections**: Collections with `isPublic: true` are accessible via `/api/public/collections/{id}` without auth. Non-public collections return 404 (not 403) on public endpoints to avoid leaking existence.

8. **Search behavior**: Search is case-insensitive, partial match (LIKE/contains). It searches across link `name`, `url`, `description`, and associated tag names. Results only include links the user has access to (own + shared collections).

9. **Duplicate links allowed**: Multiple links with the same URL can exist in the same collection. No uniqueness constraint on URL.

10. **Collection color**: Stored as a hex string (e.g., "#ff0000"). Optional field, defaults to null.
