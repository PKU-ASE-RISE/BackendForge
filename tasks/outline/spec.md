# Outline — Backend Implementation Spec

## Overview

Outline is a **collaborative knowledge base and wiki** (based on [Outline](https://github.com/outline/outline), 29K+ stars). Teams create collections of documents with rich markdown content, nested hierarchies, full-text search, sharing, and fine-grained permissions.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based API key auth (simplified from the original Outline token system):

- `X-Api-Key`: API key identifying the user

Rules:
- The `X-Api-Key` header is required on all endpoints **except** `POST /shares.info` (public share access).
- If the header is missing on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — the key IS the user identifier. If a user with that key doesn't exist, **auto-create** the user (role=admin for the first user, role=member for subsequent users). A default team is auto-created with the first user.
- **Data scoping**: All data is scoped to the team. All auto-created users belong to the same team.
- **Role-based access**:
  - `admin`: Full access to everything.
  - `member`: Can create/edit documents in read_write collections, view documents in read collections. Cannot manage users or team settings.
  - `viewer`: Can only view published documents. Cannot create or edit.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (40 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

All endpoints use `POST` method with JSON request body (following Outline's API convention). Responses are JSON with a `data` wrapper object.

---

### 1. Documents — knowledge base content (9 endpoints)

Documents are the core entity — markdown content organized in collections with hierarchy support.

- `POST /documents.create` — Create a document (title, text, collectionId required; optional parentDocumentId, publish, template)
- `POST /documents.info` — Get a document by id
- `POST /documents.update` — Update a document (id required; optional title, text, publish, done, archived)
- `POST /documents.delete` — Soft-delete a document (moves to trash)
- `POST /documents.list` — List documents (supports collectionId filter, offset/limit pagination)
- `POST /documents.search` — Full-text search (query required; returns ranked results with context)
- `POST /documents.drafts` — List unpublished draft documents for current user
- `POST /documents.archive` — Archive a document (and all children)
- `POST /documents.move` — Move a document to a different collection or parent

### 2. Collections — document containers (5 endpoints)

Collections organize documents and define access permissions.

- `POST /collections.create` — Create a collection (name required; optional description, color, permission, sort)
- `POST /collections.info` — Get a collection by id
- `POST /collections.update` — Update a collection
- `POST /collections.delete` — Delete a collection (and all documents in it)
- `POST /collections.list` — List all collections

### 3. Users — team member profiles (3 endpoints)

- `POST /users.info` — Get a user by id
- `POST /users.list` — List all users in the team (admin only)
- `POST /users.update` — Update a user's role or suspend them (admin only)

### 4. Teams — workspace settings (2 endpoints)

- `POST /teams.info` — Get the current team info
- `POST /teams.update` — Update team settings (admin only)

### 5. Shares — public document links (3 endpoints)

- `POST /shares.create` — Create a public share link for a document
- `POST /shares.list` — List all shares
- `POST /shares.info` — Get shared document content (NO auth required — public access)
- `POST /shares.revoke` — Revoke a share link

### 6. Revisions — document edit history (2 endpoints)

- `POST /revisions.list` — List revisions for a document
- `POST /revisions.info` — Get a specific revision

### 7. Stars — user favorites (3 endpoints)

- `POST /stars.create` — Star a document or collection
- `POST /stars.list` — List current user's stars
- `POST /stars.delete` — Remove a star

### 8. Comments — document discussions (4 endpoints)

- `POST /comments.create` — Add a comment to a document
- `POST /comments.list` — List comments on a document
- `POST /comments.update` — Update a comment (text or resolved status)
- `POST /comments.delete` — Delete a comment

### 9. Pins — highlighted documents (3 endpoints)

- `POST /pins.create` — Pin a document within a collection
- `POST /pins.list` — List pins in a collection
- `POST /pins.delete` — Remove a pin

### 10. Groups — permission groups (3 endpoints)

- `POST /groups.create` — Create a named group
- `POST /groups.list` — List all groups
- `POST /groups.delete` — Delete a group

### 11. Group Memberships — group member management (3 endpoints)

- `POST /group_memberships.create` — Add a user to a group
- `POST /group_memberships.list` — List members of a group
- `POST /group_memberships.delete` — Remove a user from a group

---

**Totals: 40 endpoints across 11 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 40 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create users and team**: When the first request arrives with `X-Api-Key: somevalue`, auto-create a team and a user (admin role). Subsequent new keys auto-create users with `member` role in the same team.

2. **Document hierarchy**: Documents can have a `parentDocumentId` pointing to another document in the same collection. Children inherit the collection. Maximum nesting is not enforced but the hierarchy must be consistent.

3. **Moving documents**: When a document is moved to a different collection (via `documents.move`), all its descendants also move to the new collection. `parentDocumentId` can also be changed.

4. **Archiving cascades**: Archiving a document also archives all its child documents (recursively). Archived documents don't appear in `documents.list` by default.

5. **Soft delete**: `documents.delete` marks a document as deleted (soft delete) but it remains in the database. It no longer appears in any listing. All children are also soft-deleted.

6. **Publishing**: Documents start as drafts (publishedAt = null) unless `publish: true` is passed at creation. Draft documents only appear in `documents.drafts` for their creator. Published documents appear in `documents.list`.

7. **Templates**: Documents marked as `template: true` don't appear in `documents.list` or `documents.search`. They are only accessible via `documents.info` by their ID.

8. **Collection permissions**:
   - `read_write` (default): Members can create and edit documents.
   - `read`: Members can only view documents, not create or edit.
   - Admins always have full access regardless of collection permission.
   - Viewers can only read published documents in any collection.

9. **Share links**: Creating a share generates a unique URL token. `shares.info` with that token returns the document content without requiring authentication. Optional `includeChildDocuments: true` also returns child documents.

10. **Search ranking**: `documents.search` performs full-text search. Title matches rank higher than content matches. Results include a `context` field with a text snippet showing where the match occurred (substring of the matching text, ~50 chars around the match).

11. **Revisions**: Every time a document is updated (text or title changes), a new revision is created automatically. Revisions store the previous title and text. They are listed newest-first.

12. **Stars**: A user can star a document or collection. Stars are per-user. A user cannot star the same item twice (return 400).

13. **Comments**: Comments belong to a document and a user. The `resolved` flag (default false) can be toggled. Only the comment author or an admin can update/delete a comment.

14. **Pins**: A document can be pinned within its collection. Each document can only be pinned once per collection (return 400 on duplicate). Pins have an optional `index` for ordering.

15. **Groups**: Named groups of users. Group names must be unique within the team (return 400 on duplicate).

16. **Group Memberships**: Users can be added to groups. A user cannot be added to the same group twice (return 400).

17. **Pagination**: List endpoints support `offset` (default 0) and `limit` (default 25, max 100). Response includes a `pagination` object with `offset`, `limit`, and `total` (total count).

18. **ID format**: All IDs are UUIDs (v4).
