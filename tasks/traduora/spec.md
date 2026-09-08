# Traduora — Backend Implementation Spec

## Overview

Traduora is a **translation management platform** (based on [Traduora](https://github.com/ever-co/ever-traduora), 2.1K stars). Teams create projects, define locales and terms (translation keys), and manage translated strings for each term-locale pair. It supports import/export in JSON/YAML formats, team collaboration with role-based access, and translation progress statistics.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-Api-Key`: API key identifying the user

Rules:
- The `X-Api-Key` header is required on every endpoint.
- If the header is missing or empty, return `401 Unauthorized`.
- Trust the header value directly — the key IS the user identity. If a user with that key doesn't exist, **auto-create** the user with that key as their name/identifier. The user's ID equals the key value.
- **Data scoping**: Projects are scoped by membership. A user can only see/access projects where they are an owner or invited member. The project creator is automatically the owner (admin role).

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (15 paths, 30 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Projects — CRUD (2 paths, 5 methods)

Projects are the top-level container for all translation work.

- `GET /api/v1/projects` — List all projects the user is a member of
- `POST /api/v1/projects` — Create a new project (body: `name`, optional `description`). Returns `201`.
- `GET /api/v1/projects/{projectId}` — Get project details
- `PATCH /api/v1/projects/{projectId}` — Update project name/description (admin only)
- `DELETE /api/v1/projects/{projectId}` — Delete project (admin only). Returns `204`.

### 2. Locales — per-project language management (2 paths, 3 methods)

Locales define which languages a project supports.

- `GET /api/v1/projects/{projectId}/locales` — List all locales in a project
- `POST /api/v1/projects/{projectId}/locales` — Add a locale (body: `code`; admin only). Returns `201`.
- `DELETE /api/v1/projects/{projectId}/locales/{localeCode}` — Remove a locale (admin only). Returns `204`.

### 3. Terms — translation keys (2 paths, 5 methods)

Terms are the translation keys (e.g., `home.welcome_message`, `errors.not_found`).

- `GET /api/v1/projects/{projectId}/terms` — List terms (supports `search` query param for substring filter)
- `POST /api/v1/projects/{projectId}/terms` — Create a term (body: `value`, optional `description`; admin/editor). Returns `201`.
- `GET /api/v1/projects/{projectId}/terms/{termId}` — Get a single term
- `PATCH /api/v1/projects/{projectId}/terms/{termId}` — Update a term (admin/editor)
- `DELETE /api/v1/projects/{projectId}/terms/{termId}` — Delete a term (admin/editor). Returns `204`.

### 4. Translations — per (term, locale) pair (2 paths, 3 methods)

A translation maps a (term, locale) pair to a translated string.

- `GET /api/v1/projects/{projectId}/translations/{localeCode}` — Get all translations for a locale (includes all terms, untranslated = empty string)
- `GET /api/v1/projects/{projectId}/translations/{localeCode}/{termId}` — Get a single translation
- `PATCH /api/v1/projects/{projectId}/translations/{localeCode}/{termId}` — Set/update a translation (body: `value`; admin/editor)

### 5. Import/Export — bulk operations (2 paths, 2 methods)

- `POST /api/v1/projects/{projectId}/imports` — Import translations (body: `locale`, `format`, `data`; admin/editor)
- `GET /api/v1/projects/{projectId}/exports` — Export translations (query params: `locale`, `format`)

### 6. Project Members — collaboration (2 paths, 4 methods)

- `GET /api/v1/projects/{projectId}/members` — List all members
- `POST /api/v1/projects/{projectId}/members` — Add a member (body: `userId`, `role`; admin only). Returns `201`.
- `PATCH /api/v1/projects/{projectId}/members/{userId}` — Update member role (admin only)
- `DELETE /api/v1/projects/{projectId}/members/{userId}` — Remove a member (admin only). Returns `204`.

### 7. Labels — organize terms (2 paths, 5 methods)

- `GET /api/v1/projects/{projectId}/labels` — List all labels
- `POST /api/v1/projects/{projectId}/labels` — Create a label (body: `value`, optional `color`; admin/editor). Returns `201`.
- `GET /api/v1/projects/{projectId}/labels/{labelId}` — Get a single label
- `PATCH /api/v1/projects/{projectId}/labels/{labelId}` — Update a label (admin/editor)
- `DELETE /api/v1/projects/{projectId}/labels/{labelId}` — Delete a label (admin/editor). Returns `204`.

### 8. Term Labels — tag terms with labels (2 paths, 2 methods)

- `POST /api/v1/projects/{projectId}/terms/{termId}/labels` — Attach a label to a term (body: `labelId`; admin/editor). Returns `200`.
- `DELETE /api/v1/projects/{projectId}/terms/{termId}/labels/{labelId}` — Detach a label from a term (admin/editor). Returns `204`.

### 9. Statistics — translation progress (1 path, 1 method)

- `GET /api/v1/projects/{projectId}/stats` — Get per-locale translation progress

---

**Totals: 15 paths, 30 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 15 paths / 30 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create users**: When a request comes in with `X-Api-Key: somevalue`, if no user with that identifier exists, automatically create that user. The key IS both the user ID and the user name.

2. **Project ownership**: The user who creates a project automatically becomes an `admin` member of that project AND is flagged as the owner. They can then invite others.

3. **Role-based access control (RBAC)**:
   - `admin` — Full access: update/delete project, manage members, manage locales, CRUD terms, set translations, manage labels, import/export
   - `editor` — Can CRUD terms, set translations, manage labels, and import. Cannot update/delete project, manage members, or manage locales.
   - `viewer` — Read-only access: can list/get projects, locales, terms, translations, labels, stats, and export. Cannot create/update/delete anything.

4. **Term uniqueness**: Terms are unique by `value` within a project. Creating a duplicate term returns `400 Bad Request`.

5. **Translation defaults**: Untranslated terms return an empty string `""` for their translation value, NOT a 404 error. Every term-locale pair is always queryable and returns `200` with an empty value if no translation has been set.

6. **Import merging**: Import is additive/merge:
   - If a term exists and the import provides a different translation value, update the translation (`translationsUpdated++`).
   - If a term exists and the import provides the same translation value, skip it (no increment).
   - If a term does NOT exist, auto-create it (`termsCreated++`) and set its translation (`translationsCreated++`).
   - Terms/translations NOT in the import payload are left unchanged (merge, not replace).
   - Return: `{ "termsCreated": N, "translationsCreated": N, "translationsUpdated": N }`

7. **Export formats**:
   - `json` — flat key-value object: `{"term.value": "translated string", ...}`. Untranslated terms have empty string value.
   - `nested_json` — dot-separated term values become nested objects. E.g., term `"menu.file"` with translation `"File"` exports as `{"menu": {"file": "File"}}`.
   - `yaml` — same structure as nested_json but serialized as YAML.

8. **Statistics calculation**: For each locale in the project:
   - `locale`: the locale code
   - `totalCount`: total number of terms in the project
   - `translatedCount`: number of terms that have a non-empty translation string
   - `progress`: percentage = `round(translatedCount / totalCount * 100, 1)`. If totalCount is 0, progress is 0.

9. **Project access**: Users can only access projects they are a member of. Accessing a project where the user has no membership returns `404 Not Found` (not 403).

10. **Owner cannot be removed**: The project creator (owner) cannot be removed from the project. Return `400 Bad Request`.

11. **Self-removal**: A member cannot remove themselves from a project. Return `400 Bad Request`.

12. **Cascade deletes**:
    - Deleting a project deletes all its locales, terms, translations, labels, memberships
    - Deleting a locale deletes all translations for that locale in the project
    - Deleting a term deletes all its translations and all term-label associations
    - Deleting a label removes it from all terms (term-label associations deleted)

13. **Label uniqueness**: Labels are unique by `value` within a project. Creating a duplicate returns `400 Bad Request`.

14. **Label colors**: Label colors are optional hex strings (e.g., `#ff0000`). Default to `#000000` if not provided.

15. **Locale code validation**: Locale codes must match the regex `^[a-z]{2}(_[A-Z]{2})?$` (e.g., `en`, `fr`, `de`, `en_US`, `pt_BR`). Invalid codes return `400 Bad Request`. Adding a locale that already exists returns `400 Bad Request`.

16. **Search terms**: The `search` query parameter on `GET /terms` filters terms whose `value` contains the search string (case-insensitive substring match).

17. **Term labels**: Adding a label to a term that already has it returns `400 Bad Request`. Removing a label not on the term returns `404 Not Found`.

18. **Adding members**: Adding a user who is already a member returns `400 Bad Request`. The `userId` in the request body is the user's key/identifier.

19. **Response wrapper**: All responses that return data use a `{"data": ...}` wrapper. The only exceptions are: export (returns raw JSON/YAML), and delete operations (return `204` with no body).
