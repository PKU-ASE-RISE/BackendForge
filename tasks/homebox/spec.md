# Homebox — Backend Implementation Spec

## Overview

Homebox is a **home inventory management system** (based on [Homebox](https://github.com/sysadminsmedia/homebox), 3.5K stars). Users track items in their home, organize them by locations and labels, log maintenance activities, attach documents, and get statistics about their inventory.

The application supports multi-user within groups, hierarchical locations, label-based organization, and CSV import/export.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified from the original Homebox JWT system):

- `X-User-Id`: UUID identifying the user
- `X-Group-Id`: UUID identifying the group

Rules:
- Both headers are required on all endpoints **except** `/health`.
- If either header is missing on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — no database validation of users/groups. If a user/group combination is seen for the first time, treat it as a new user in that group.
- **Data scoping**: All data is scoped to the group (`X-Group-Id`). Users in the same group share data. Users in different groups cannot see each other's data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (30+ paths, 35+ endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Items — core inventory management (5 paths, 6 methods)

Items are the central entity in the system.

- `GET /items` — List items (supports `q` search, `labels` filter, `locationId` filter, `archived` filter, pagination with `page`/`pageSize`)
- `POST /items` — Create an item (body: `name`, optional fields)
- `GET /items/{id}` — Get a single item with full details
- `PUT /items/{id}` — Update an item
- `DELETE /items/{id}` — Delete an item (also deletes attachments, maintenance logs, label associations)
- `PATCH /items/{id}/archive` — Archive or unarchive an item (body: `archived`)

### 2. Locations — hierarchical organization (3 paths, 5 methods)

Locations represent physical places (houses, rooms, shelves, drawers).

- `GET /locations` — List all locations (flat list with parent info)
- `POST /locations` — Create a location (body: `name`, optional `description`, `parentId`)
- `GET /locations/{id}` — Get a location with children and item count
- `PUT /locations/{id}` — Update a location (can change parent)
- `DELETE /locations/{id}` — Delete a location (fails if it has items or children)

### 3. Labels — color-coded tags (3 paths, 5 methods)

Labels are tags that can be attached to items for categorization.

- `GET /labels` — List all labels
- `POST /labels` — Create a label (body: `name`, optional `description`, `color`)
- `GET /labels/{id}` — Get a label with item count
- `PUT /labels/{id}` — Update a label
- `DELETE /labels/{id}` — Delete a label (removes from all items)

### 4. Item Labels — attach/detach labels (1 path, 2 methods)

- `POST /items/{id}/labels` — Attach a label to an item (body: `labelId`)
- `DELETE /items/{id}/labels/{labelId}` — Detach a label from an item

### 5. Item Attachments — document management (2 paths, 4 methods)

Attachments are metadata records for documents associated with items.

- `GET /items/{id}/attachments` — List attachments for an item
- `POST /items/{id}/attachments` — Create an attachment (body: `name`, `type`)
- `PUT /items/{id}/attachments/{attachmentId}` — Update an attachment
- `DELETE /items/{id}/attachments/{attachmentId}` — Delete an attachment

### 6. Maintenance Log — service history (2 paths, 4 methods)

Track maintenance and service activities for items.

- `GET /items/{id}/maintenance` — List maintenance entries for an item
- `POST /items/{id}/maintenance` — Create a maintenance entry (body: `date`, `description`, optional `cost`, `scheduledDate`)
- `PUT /items/{id}/maintenance/{maintenanceId}` — Update a maintenance entry
- `DELETE /items/{id}/maintenance/{maintenanceId}` — Delete a maintenance entry

### 7. Statistics — inventory overview (1 path, 1 method)

- `GET /statistics` — Get group statistics (totalItems, totalValue, itemsByLocation, itemsByLabel)

### 8. Import/Export — CSV data transfer (2 paths, 2 methods)

- `POST /import/csv` — Import items from CSV (body: JSON array of item objects)
- `GET /export/csv` — Export all items as JSON array (CSV-ready format)

### 9. Health — system status (1 path, 1 method)

- `GET /health` — Returns health status (no auth required)

---

**Totals: 20 paths, 35 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 20 paths / 35 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Group-scoped data**: All data belongs to a group. Users in the same group share all data (items, locations, labels). Different groups are completely isolated.

2. **Location hierarchy**: Locations can have a `parentId` referencing another location. This forms a tree. A location cannot be its own parent. Circular references must be prevented.

3. **Delete location restrictions**: A location cannot be deleted if it has any items assigned to it OR if it has child locations. Return `409 Conflict`.

4. **Items by location (statistics)**: The count includes items in ALL sub-locations recursively. E.g., if "House" has "Room" which has 3 items, "House" count includes those 3 items.

5. **Total value**: Computed as sum of (`purchasePrice` * `quantity`) across all non-archived items in the group.

6. **Archived items excluded from statistics**: Archived items are NOT counted in `totalItems`, `totalValue`, `itemsByLocation`, or `itemsByLabel`.

7. **Archived filter**: `GET /items` defaults to showing only non-archived items. Pass `?archived=true` to see only archived items. Pass `?archived=all` to see everything.

8. **Label filtering**: `GET /items?labels=id1,id2` returns items that have ANY of the specified labels (OR logic).

9. **Search**: `GET /items?q=term` searches item `name`, `description`, `serialNumber`, and `modelNumber` fields (case-insensitive substring match).

10. **CSV Import**: The import endpoint accepts a JSON array of item objects. Each object should have at minimum a `name` field. The endpoint creates items and returns the count of created items. Fields map directly to item fields. If a `locationName` is provided instead of `locationId`, look up the location by name within the group (or ignore if not found).

11. **CSV Export**: Returns all non-archived items as a JSON array with all fields flattened (including `locationName` and `labelNames` as a comma-separated string).

12. **Attachment types**: Valid types are `manual`, `receipt`, `warranty`, `photo`. Invalid types should return `400 Bad Request`.

13. **Label color format**: Colors should be stored as provided (typically hex like `#ff0000`). No validation required on format.

14. **Pagination**: `GET /items` supports `page` (1-indexed, default 1) and `pageSize` (default 20, max 100). Response includes pagination metadata.

15. **Item quantity**: Defaults to 1 if not specified. Must be >= 1.

16. **Maintenance cost**: Stored as a decimal/float. Can be 0 or positive.

17. **Warranty tracking**: Items where `warrantyExpires` is a date in the past are considered "expired warranty". This is informational only — no special API behavior, but the field must be stored and returned correctly.

18. **Unique constraints**: Location names must be unique within the same parent (including root level) within a group. Label names must be unique within a group. Return `409 Conflict` on duplicates.
