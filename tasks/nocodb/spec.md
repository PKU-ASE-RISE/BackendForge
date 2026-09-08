# NocoDB — No-Code Database Platform API

## Overview

NocoDB turns databases into smart spreadsheets. It provides a REST API to manage bases (projects), tables, typed columns, records (rows), views with filtering/sorting, shared views, webhooks, comments, and audit logging.

## Authentication

All endpoints require an `X-API-Key` header (except shared view access which uses a UUID token).

- Missing or empty `X-API-Key` → 401 Unauthorized
- API key format: `{role}_{baseId}_{userId}` (e.g., `owner_base1_user1`)
- Roles (hierarchical): owner > creator > editor > commenter > viewer
  - **viewer**: read bases, tables, columns, records, views
  - **commenter**: viewer + create/read comments
  - **editor**: commenter + create/update/delete records
  - **creator**: editor + create/update/delete tables, columns, views, filters, sorts
  - **owner**: creator + manage base settings, shares, hooks, delete base

If the role in the API key does not have sufficient permissions for the operation → 403 Forbidden.

The `baseId` in the API key must match the base being accessed. A mismatch → 403.

## Data Model

### Base
A base is the top-level container (like a project/workspace).

Fields: `id`, `title`, `description`, `createdAt`, `updatedAt`

### Table
A table belongs to a base and contains columns and records.

Fields: `id`, `baseId`, `title`, `description`, `createdAt`, `updatedAt`

### Column
A column defines a field in a table. Every table starts with no user-defined columns.

Fields: `id`, `tableId`, `title`, `type`, `options` (type-specific), `order`, `createdAt`, `updatedAt`

Supported types:
- **text**: plain text
- **number**: numeric values (integer or float)
- **email**: validated email format
- **url**: validated URL format
- **date**: ISO 8601 date string
- **checkbox**: boolean (true/false)
- **singleSelect**: one value from predefined options. `options.choices` = list of strings.
- **multiSelect**: multiple values from predefined options. `options.choices` = list of strings.
- **attachment**: list of objects with `name` and `url`
- **link**: relation to another table. `options.linkedTableId` = target table ID. Creates a many-to-many relationship.
- **formula**: computed field. `options.expression` = formula string. Supported: `CONCAT(f1, " ", f2)`, `IF(f > X, "yes", "no")`, `LEN(f)`, `UPPER(f)`, `ADD(f1, f2)`
- **lookup**: pull field through relation. `options.linkColumnId` + `options.lookupColumnId`
- **rollup**: aggregate linked records. `options.linkColumnId` + `options.rollupColumnId` + `options.aggregation` (COUNT, SUM, AVG)

### Record
A row in a table. Has a system `id` field plus dynamic fields matching column titles.

Fields: `id`, plus one key per column title with the value.

### View
A view is a saved configuration for displaying table records. Types: grid, form, gallery, kanban.

Fields: `id`, `tableId`, `title`, `type`, `createdAt`, `updatedAt`

When querying records through a view, filters and sorts associated with that view are applied.

### Filter
A filter condition applied to a view.

Fields: `id`, `viewId`, `columnId`, `operator`, `value`

Operators: `eq`, `neq`, `gt`, `lt`, `gte`, `lte`, `contains`, `notContains`, `is_null`, `is_not_null`

### Sort
A sort rule applied to a view.

Fields: `id`, `viewId`, `columnId`, `direction` (`asc` or `desc`)

### Share
A public sharing link for a view.

Fields: `id`, `viewId`, `uuid` (auto-generated), `password` (optional), `createdAt`

Shared views are accessed via `/api/v1/shared/{uuid}/records` without authentication. If a password is set, it must be provided as a query parameter `password`.

### Hook (Webhook)
A webhook triggered on record events.

Fields: `id`, `tableId`, `title`, `event` (record.created, record.updated, record.deleted), `url`, `enabled`, `createdAt`, `updatedAt`

### Comment
A comment on a specific record.

Fields: `id`, `recordId`, `userId`, `body`, `createdAt`

### Audit Log Entry
Tracks changes to records.

Fields: `id`, `baseId`, `tableId`, `recordId`, `userId`, `action` (created, updated, deleted), `timestamp`, `changes` (object showing what changed)

## API Endpoints (49 total)

### Bases
- `POST /api/v1/bases` — Create a base (owner/creator)
- `GET /api/v1/bases` — List bases accessible to user
- `GET /api/v1/bases/{baseId}` — Get base details
- `PATCH /api/v1/bases/{baseId}` — Update base (owner)
- `DELETE /api/v1/bases/{baseId}` — Delete base (owner)
- `GET /api/v1/bases/{baseId}/audit` — Get audit log (owner/creator)

### Tables
- `POST /api/v1/bases/{baseId}/tables` — Create table (creator+)
- `GET /api/v1/bases/{baseId}/tables` — List tables
- `GET /api/v1/bases/{baseId}/tables/{tableId}` — Get table with columns
- `PATCH /api/v1/bases/{baseId}/tables/{tableId}` — Update table (creator+)
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}` — Delete table (creator+)

### Columns
- `POST /api/v1/bases/{baseId}/tables/{tableId}/columns` — Create column (creator+)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/columns` — List columns
- `GET /api/v1/bases/{baseId}/tables/{tableId}/columns/{columnId}` — Get column
- `PATCH /api/v1/bases/{baseId}/tables/{tableId}/columns/{columnId}` — Update column (creator+)
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}/columns/{columnId}` — Delete column (creator+)

### Records
- `POST /api/v1/bases/{baseId}/tables/{tableId}/records` — Create record (editor+)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/records` — List records
- `GET /api/v1/bases/{baseId}/tables/{tableId}/records/{recordId}` — Get record
- `PATCH /api/v1/bases/{baseId}/tables/{tableId}/records/{recordId}` — Update record (editor+)
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}/records/{recordId}` — Delete record (editor+)

### Views
- `POST /api/v1/bases/{baseId}/tables/{tableId}/views` — Create view (creator+)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/views` — List views
- `GET /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}` — Get view
- `PATCH /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}` — Update view (creator+)
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}` — Delete view (creator+)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/records` — List records through view (applies filters/sorts)

### Filters
- `POST /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/filters` — Create filter (creator+)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/filters` — List filters
- `GET /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/filters/{filterId}` — Get filter
- `PATCH /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/filters/{filterId}` — Update filter (creator+)
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/filters/{filterId}` — Delete filter (creator+)

### Sorts
- `POST /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/sorts` — Create sort (creator+)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/sorts` — List sorts
- `GET /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/sorts/{sortId}` — Get sort
- `PATCH /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/sorts/{sortId}` — Update sort (creator+)
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/sorts/{sortId}` — Delete sort (creator+)

### Shares
- `POST /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/shares` — Create share (owner)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/shares` — List shares (owner)
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}/views/{viewId}/shares/{shareId}` — Delete share (owner)

### Shared View Access
- `GET /api/v1/shared/{uuid}/records` — Access shared view records (no auth needed, password if set)

### Hooks
- `POST /api/v1/bases/{baseId}/tables/{tableId}/hooks` — Create hook (owner)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/hooks` — List hooks (owner)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/hooks/{hookId}` — Get hook (owner)
- `PATCH /api/v1/bases/{baseId}/tables/{tableId}/hooks/{hookId}` — Update hook (owner)
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}/hooks/{hookId}` — Delete hook (owner)

### Comments
- `POST /api/v1/bases/{baseId}/tables/{tableId}/records/{recordId}/comments` — Create comment (commenter+)
- `GET /api/v1/bases/{baseId}/tables/{tableId}/records/{recordId}/comments` — List comments
- `DELETE /api/v1/bases/{baseId}/tables/{tableId}/records/{recordId}/comments/{commentId}` — Delete comment (owner)

## Business Logic Details

### Formula Evaluation
Formula fields are computed on read. Supported functions:
- `CONCAT(val1, val2, ...)` — concatenate strings/values
- `IF(condition, trueVal, falseVal)` — conditional. Condition format: `fieldName > value` or `fieldName == value`
- `LEN(field)` — length of text field
- `UPPER(field)` — uppercase text
- `ADD(field1, field2)` — sum two numeric fields

### Link Fields
When a link column is created between Table A and Table B:
- Records in Table A gain a field that holds an array of linked record IDs from Table B
- Records in Table B gain a corresponding field (auto-created reciprocal link column)
- Setting links: provide array of record IDs when creating/updating records

### Lookup Fields
- Reference a link column and a column in the linked table
- Value is computed by following the link and returning the referenced field values as an array

### Rollup Fields
- Reference a link column and a numeric column in the linked table
- Aggregation: COUNT (count linked records), SUM (sum field values), AVG (average field values)

### View Record Filtering
When fetching records through a view endpoint:
1. Apply all filter conditions (AND logic between multiple filters)
2. Apply all sort rules (in order of creation)
3. Return filtered/sorted records

### Audit Trail
Record create/update/delete operations generate audit log entries automatically. The audit log captures:
- Which user performed the action
- What changed (for updates: old and new values)
- When it happened

## Response Format

All responses use JSON. Lists are wrapped: `{ "items": [...] }` (or `{ "records": [...] }` for record lists).

Successful creation → 201. Successful update/get → 200. Successful delete → 204.

Errors return: `{ "error": "description" }` with appropriate HTTP status code.
