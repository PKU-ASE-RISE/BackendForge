# BookStack — Backend Implementation Spec

## Overview

BookStack is a **wiki/knowledge base with hierarchical content organization** (based on [BookStack](https://github.com/BookStackApp/BookStack), 16K+ stars). Content is organized in a hierarchy: Shelves contain Books, Books contain Chapters, Chapters contain Pages. Pages can also be direct children of Books (without a Chapter).

The application provides full-text search, page revision history, attachments, tagging, and a recycle bin for soft-deleted content.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified from the original BookStack token system):

- `X-Api-Key`: API key (any non-empty string; trusted directly)
- `X-User-Id`: Numeric user ID (any positive integer; trusted directly)

Rules:
- Both headers are required on **all** endpoints.
- If either header is missing or empty, return `401 Unauthorized` with body `{"error": "Unauthorized"}`.
- Trust header values directly — no database lookup needed. The user ID is used to track `created_by` and `updated_by` fields on entities.
- **Single-tenant**: All users see all content. There is no data isolation between users.
- The user ID is stored as `created_by` on creation and `updated_by` on update.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (38 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

All endpoints are under the `/api/` prefix.

---

### 1. Shelves — top-level grouping (5 endpoints)

Shelves are the top-level organizational unit. They contain an ordered list of books.

- `GET /api/shelves` — List all shelves (returns id, name, slug, description, created_by, updated_by, created_at, updated_at)
- `POST /api/shelves` — Create a shelf (body: `name` required, optional `description`, `tags`, `books` array of book IDs for ordering)
- `GET /api/shelves/{id}` — Get a shelf with its books listed
- `PUT /api/shelves/{id}` — Update a shelf (body: optional `name`, `description`, `tags`, `books`)
- `DELETE /api/shelves/{id}` — Delete a shelf (moves to recycle bin)

### 2. Books — containers for chapters and pages (5 endpoints)

Books are the primary content container. They hold chapters and direct pages.

- `GET /api/books` — List all books
- `POST /api/books` — Create a book (body: `name` required, optional `description`, `tags`)
- `GET /api/books/{id}` — Get a book with its contents (chapters and direct pages)
- `PUT /api/books/{id}` — Update a book
- `DELETE /api/books/{id}` — Delete a book (cascades to chapters/pages, moves to recycle bin)

### 3. Chapters — sections within books (5 endpoints)

Chapters group pages within a book. They have a priority (sort order) within their book.

- `GET /api/chapters` — List all chapters
- `POST /api/chapters` — Create a chapter (body: `name` required, `book_id` required, optional `description`, `priority`, `tags`)
- `GET /api/chapters/{id}` — Get a chapter with its pages
- `PUT /api/chapters/{id}` — Update a chapter
- `DELETE /api/chapters/{id}` — Delete a chapter (cascades to pages, moves to recycle bin)

### 4. Pages — content entities (8 endpoints)

Pages hold the actual content (HTML). They belong to either a chapter or directly to a book.

- `GET /api/pages` — List all pages
- `POST /api/pages` — Create a page (body: `name` required, `book_id` OR `chapter_id` required, optional `html`, `priority`, `tags`)
- `GET /api/pages/{id}` — Get a page with full content
- `PUT /api/pages/{id}` — Update a page (creates a revision)
- `DELETE /api/pages/{id}` — Delete a page (moves to recycle bin)
- `GET /api/pages/{id}/export/html` — Export page as HTML
- `GET /api/pages/{id}/export/plaintext` — Export page as plain text (strips HTML tags)
- `GET /api/pages/{id}/export/markdown` — Export page as markdown

### 5. Search — full-text search (1 endpoint)

- `GET /api/search` — Search across all content types. Query param: `query` (required). Returns matching shelves, books, chapters, and pages with relevance scores.

### 6. Attachments — file/link attachments on pages (5 endpoints)

Attachments are links or file references attached to pages.

- `GET /api/attachments` — List all attachments
- `POST /api/attachments` — Create an attachment (body: `name` required, `uploaded_to` page ID required, `type` = "link", `link_url` for link type)
- `GET /api/attachments/{id}` — Get attachment details
- `PUT /api/attachments/{id}` — Update an attachment
- `DELETE /api/attachments/{id}` — Delete an attachment

### 7. Revisions — page edit history (3 endpoints)

Every page edit creates a revision. Revisions track changes over time.

- `GET /api/pages/{id}/revisions` — List revisions for a page (newest first)
- `GET /api/pages/{id}/revisions/{rev_id}` — Get a specific revision with content
- `PUT /api/pages/{id}/revisions/{rev_id}/restore` — Restore a revision (replaces current page content, creates new revision)

### 8. Recycle Bin — soft-deleted items (3 endpoints)

Deleted items are moved to the recycle bin and can be restored.

- `GET /api/recycle-bin` — List all items in recycle bin
- `PUT /api/recycle-bin/{id}/restore` — Restore a deleted item
- `DELETE /api/recycle-bin/{id}` — Permanently delete an item from recycle bin

### 9. Content Move — reorganize content (1 endpoint)

- `PUT /api/pages/{id}/move` — Move a page to a different chapter or book (body: `chapter_id` or `book_id`)

---

**Totals: 36 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 36 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Content hierarchy**: Shelf -> Book -> Chapter -> Page. Pages can also be direct children of books (no chapter). A page has either `chapter_id` set OR `book_id` set directly (if `chapter_id` is set, `book_id` is derived from the chapter's book).

2. **Slug generation**: Every entity (shelf, book, chapter, page) has a `slug` field auto-generated from its `name`. The slug is the name lowercased, with spaces replaced by dashes, non-alphanumeric characters (except dashes) removed, and truncated to 100 characters. Slugs must be unique per entity type. If a slug collision occurs, append `-N` (where N is an incrementing number starting at 1).

3. **Priority (sort order)**: Chapters within a book and pages within a chapter/book have a `priority` field (integer, default 0). Lower priority = appears first. When listing contents of a book or chapter, items are sorted by priority ascending, then by name ascending.

4. **Revisions**: Every `PUT /api/pages/{id}` that changes `name` or `html` creates a new revision storing the **previous** content. Revisions are limited to the last 50 per page (oldest are automatically pruned when the limit is exceeded). Each revision stores: revision_number (incrementing), page_id, name, html, created_by, created_at.

5. **Restore revision**: `PUT /api/pages/{id}/revisions/{rev_id}/restore` replaces the current page content with the revision's content and creates a new revision (storing what was just replaced).

6. **Recycle bin (soft delete)**: When an entity is deleted via its DELETE endpoint, it is soft-deleted (marked as deleted with a timestamp). Soft-deleted items do not appear in normal list/get endpoints. They appear in `GET /api/recycle-bin`. Items can be restored or permanently deleted.

7. **Cascade soft-delete**: Deleting a book soft-deletes all its chapters and pages. Deleting a chapter soft-deletes all its pages. Deleting a shelf does NOT delete its books (only removes the shelf-book association).

8. **Restore from recycle bin**: Restoring an item also restores its children that were cascade-deleted with it. Restoring a book restores its chapters and pages. Restoring a chapter restores its pages.

9. **Tags**: Tags are key-value pairs attached to any entity (shelf, book, chapter, page). They are passed as an array of `{"name": "key", "value": "val"}` objects in create/update requests. Tags are returned in get responses. Tags are fully replaced on update (not merged).

10. **Search ranking**: The search endpoint performs full-text search across names and content (html for pages, description for others). Results are grouped by type. Title/name matches rank higher than content/description matches. The response includes a `total` count and results array with `type`, `id`, `name`, `slug`, and a `score` field.

11. **Timestamps**: All entities have `created_at` and `updated_at` fields (ISO 8601 format with timezone, e.g., `2024-01-15T10:30:00Z`). These are set automatically by the server.

12. **Page export**:
    - HTML export returns the raw `html` field content with Content-Type `text/html`.
    - Plaintext export strips all HTML tags and returns Content-Type `text/plain`.
    - Markdown export converts HTML to a basic markdown representation (or returns stripped text) with Content-Type `text/markdown`.

13. **Books on shelves**: The `books` field on shelf create/update is an array of book IDs specifying which books are on this shelf and their order. A book can be on multiple shelves. The shelf detail response includes the full book objects in the specified order.

14. **Attachment types**: Only `"link"` type is supported for this implementation. Link attachments require a `link_url` field.

15. **List responses**: All list endpoints return an object with `data` (array of items) and `total` (total count). Example: `{"data": [...], "total": 5}`.

16. **Create returns 200**: All successful create operations return HTTP 200 (not 201), consistent with the real BookStack API.

17. **Not found**: Accessing a non-existent or soft-deleted entity returns 404 with body `{"error": "Not Found"}`.

18. **Validation errors**: Missing required fields or invalid data returns 422 with body `{"error": "Validation failed", "details": {"field": "message"}}`.
