# Paperless-ngx — Backend Implementation Spec

## Overview

Paperless-ngx is a **document management system** (based on [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx), 40.1K stars). Users manage documents with rich metadata — correspondents, document types, tags, custom fields — with auto-matching rules and full-text search. This simplified version focuses on metadata management: documents are text-only (title + content), no file upload or OCR.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based API key authentication:

- `X-Api-Key`: API key identifying the user

Rules:
- The `X-Api-Key` header is required on **all** endpoints.
- If the header is missing or empty, return `401 Unauthorized`.
- Trust header values directly — the key IS the username. If a user with that name doesn't exist, **auto-create** the user on first request.
- **Data scoping**: All data (documents, correspondents, document types, tags, storage paths, custom fields, saved views) is scoped to the authenticated user. A user can only see/modify their own data.
- **Isolation**: A request with user A's key must never see or modify data belonging to user B.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (38 endpoints across 10 resource groups). Your implementation must match this contract exactly — response structure, field names, status codes.

All paginated list endpoints return: `{"count", "next", "previous", "results"}` where `count` is total items, `next`/`previous` are full URLs (or `null`), and `results` is the array of items. Query params: `page` (1-indexed, default 1), `page_size` (default 25).

---

### 1. Documents — core document management (5 endpoints)

- `GET /api/documents/` — List documents (paginated, filterable, searchable)
- `POST /api/documents/` — Create a document
- `GET /api/documents/{id}/` — Get a single document
- `PUT /api/documents/{id}/` — Update a document
- `DELETE /api/documents/{id}/` — Delete a document

### 2. Correspondents — sender/recipient management (5 endpoints)

- `GET /api/correspondents/` — List correspondents (paginated)
- `POST /api/correspondents/` — Create a correspondent
- `GET /api/correspondents/{id}/` — Get a single correspondent
- `PUT /api/correspondents/{id}/` — Update a correspondent
- `DELETE /api/correspondents/{id}/` — Delete a correspondent

### 3. Document Types — category management (5 endpoints)

- `GET /api/document_types/` — List document types (paginated)
- `POST /api/document_types/` — Create a document type
- `GET /api/document_types/{id}/` — Get a single document type
- `PUT /api/document_types/{id}/` — Update a document type
- `DELETE /api/document_types/{id}/` — Delete a document type

### 4. Tags — label management (5 endpoints)

- `GET /api/tags/` — List tags (paginated)
- `POST /api/tags/` — Create a tag
- `GET /api/tags/{id}/` — Get a single tag
- `PUT /api/tags/{id}/` — Update a tag
- `DELETE /api/tags/{id}/` — Delete a tag

### 5. Storage Paths — path template management (5 endpoints)

- `GET /api/storage_paths/` — List storage paths (paginated)
- `POST /api/storage_paths/` — Create a storage path
- `GET /api/storage_paths/{id}/` — Get a single storage path
- `PUT /api/storage_paths/{id}/` — Update a storage path
- `DELETE /api/storage_paths/{id}/` — Delete a storage path

### 6. Custom Fields — field definition management (5 endpoints)

- `GET /api/custom_fields/` — List custom field definitions (paginated)
- `POST /api/custom_fields/` — Create a custom field definition
- `GET /api/custom_fields/{id}/` — Get a single custom field
- `PUT /api/custom_fields/{id}/` — Update a custom field
- `DELETE /api/custom_fields/{id}/` — Delete a custom field

### 7. Saved Views — filter/sort presets (5 endpoints)

- `GET /api/saved_views/` — List saved views (paginated)
- `POST /api/saved_views/` — Create a saved view
- `GET /api/saved_views/{id}/` — Get a single saved view
- `PUT /api/saved_views/{id}/` — Update a saved view
- `DELETE /api/saved_views/{id}/` — Delete a saved view

### 8. Search — full-text search (1 endpoint)

- `GET /api/search/` — Search documents by content with ranking

### 9. Bulk Operations — batch modifications (1 endpoint)

- `POST /api/documents/bulk_edit/` — Perform bulk operations on multiple documents

### 10. Tasks — background task status (1 endpoint)

- `GET /api/tasks/` — List background tasks (returns empty list)

---

**Totals: 38 endpoints across 10 resource groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 38 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

### Auto-Matching Rules

1. **Matching on document creation**: When a document is created (via POST), the system checks all correspondents, document types, and tags owned by the user. If any have a `matching_algorithm` and `match` pattern set, and the document's title or content matches, they are auto-assigned.

2. **Matching algorithms** (`matching_algorithm` field):
   - `0` or `null` = **None**: No matching is performed.
   - `1` = **Any**: Matches if ANY space-separated word in the `match` field appears as a whole word in the document's title or content (case-insensitive).
   - `2` = **All**: Matches if ALL space-separated words in the `match` field appear as whole words in the document's title or content (case-insensitive).
   - `3` = **Exact**: Matches if the `match` string appears as an exact substring in the document's title or content (case-insensitive).
   - `4` = **Regex**: Matches if the `match` regex pattern finds a match in the document's title or content (case-insensitive).
   - `5` = **Fuzzy**: Same behavior as "Any" for our benchmark.

3. **Matching priority**: Auto-matching only sets fields that are NOT explicitly provided in the creation request. If the user provides `correspondent`, `document_type`, or specific `tags` in the POST body, those take precedence.

4. **Multiple matches for tags**: ALL matching tags are added to the document.

5. **Single match for correspondent/type**: If multiple correspondents (or types) match, the one with the lowest ID is assigned.

### Archive Serial Number (ASN)

6. **ASN uniqueness**: The `archive_serial_number` must be unique across all documents for a given user. Attempting to set a duplicate ASN returns `400 Bad Request`.

7. **ASN is optional**: If `archive_serial_number` is not provided when creating a document, it remains `null`. It is NOT auto-assigned.

### Document Relationships

8. **Correspondent/Type/StoragePath reference**: These fields hold the ID of an entity owned by the same user. Setting a value to an ID that doesn't exist or belongs to another user returns `400 Bad Request`.

9. **Tags reference**: A document's `tags` field is an array of tag IDs. All referenced tags must exist and belong to the same user. Invalid tag IDs return `400 Bad Request`.

### Custom Fields on Documents

10. **Custom field instances**: Documents have a `custom_fields` array. Each entry is `{"field": <custom_field_id>, "value": <value>}`. The referenced custom field must exist and belong to the same user.

11. **Value type validation**: The value must be compatible with the custom field's `data_type`:
    - `string` → any string
    - `integer` → integer value (or string that parses to int)
    - `float` → numeric value
    - `boolean` → boolean true/false
    - `date` → string in YYYY-MM-DD format
    - `url` → string (no strict validation required)
    - `monetary` → string (e.g., "EUR100.50")
    - Return `400` if value is clearly incompatible (e.g., string "hello" for integer field).

### Pagination

12. **Standard pagination**: All list endpoints use `page` (1-based, default 1) and `page_size` (default 25) query parameters. Response: `{"count": N, "next": url|null, "previous": url|null, "results": [...]}`.

13. **next/previous URLs**: Full URLs including query params, or `null` if no next/previous page exists.

### Filtering (Documents list endpoint)

14. **Filter parameters** on `GET /api/documents/`:
    - `correspondent__id=X` — exact match on correspondent
    - `document_type__id=X` — exact match on document type
    - `tags__id__all=X,Y` — document has ALL listed tags
    - `tags__id__in=X,Y` — document has at least ONE of listed tags
    - `archive_serial_number__gte=X` — ASN >= X
    - `archive_serial_number__lte=Y` — ASN <= Y
    - `title__icontains=text` — case-insensitive substring match on title
    - `content__icontains=text` — case-insensitive substring match on content
    - `ordering` — sort field, prefix `-` for descending. Valid: `id`, `title`, `created_date`, `added_date`, `archive_serial_number`

### Search

15. **Full-text search**: `GET /api/search/?query=<text>` searches title and content. Results ranked by relevance (term frequency). Returns results with `score` and `highlights`.

### Bulk Operations

16. **Bulk edit**: `POST /api/documents/bulk_edit/` accepts:
    - `documents`: array of document IDs
    - `method`: one of `set_correspondent`, `set_document_type`, `add_tag`, `remove_tag`, `delete`
    - `parameters`: object with relevant value (e.g., `{"correspondent": 5}`, `{"tag": 3}`)
    - All document IDs must belong to the current user. Any invalid ID → `400`.
    - Returns `200` with `{"result": "OK"}` on success.

### Deletion Behavior

17. **Cascading nullification**: Deleting a correspondent/type/storage_path sets references to `null` on affected documents (documents are NOT deleted).

18. **Tag removal**: Deleting a tag removes it from all documents' tag arrays.

19. **Custom field cleanup**: Deleting a custom field definition removes all instances of that field from all documents.

### Naming Rules

20. **Unique names per user**: Correspondent names, document type names, tag names, storage path names, custom field names, and saved view names must be unique per user. Duplicate → `400 Bad Request`.

### Tasks

21. **Tasks endpoint**: `GET /api/tasks/` returns an empty array `[]`. No actual background processing is needed.

### Ordering

22. **Default ordering**: All list endpoints return results ordered by `id` ascending unless `ordering` param is specified.
