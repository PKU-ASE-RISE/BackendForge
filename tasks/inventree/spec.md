# InvenTree — Backend Implementation Spec

## Overview

InvenTree is an **open-source inventory management system** (based on [InvenTree](https://github.com/inventree/InvenTree), 6.9K stars). It tracks parts, stock, suppliers, bills of materials, build orders, and purchase orders for manufacturing and hardware projects.

The application manages the full lifecycle: define parts and their sub-components (BOM), track physical stock across warehouse locations, create build orders to assemble products (consuming BOM items from stock), and purchase orders to acquire parts from suppliers.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-Api-Key`: API key for authentication

Rules:
- The `X-Api-Key` header is required on all endpoints **except** `GET /api/health`.
- If the header is missing or empty on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — any non-empty key is accepted. No database lookup needed.
- **Single-tenant**: All data is shared. There is no per-user data isolation.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (48 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Part Categories — hierarchical organization (2 paths, 5 methods)

Categories form a tree structure for organizing parts.

- `GET /api/categories` — List categories (optional `parent` filter, `search`)
- `POST /api/categories` — Create a category
- `GET /api/categories/{id}` — Get a category (includes `pathstring`)
- `PUT /api/categories/{id}` — Update a category
- `DELETE /api/categories/{id}` — Delete a category

### 2. Parts — component/product definitions (2 paths, 5 methods)

Parts are the core entity representing components, products, or assemblies.

- `GET /api/parts` — List parts (filters: `category`, `assembly`, `is_template`, `low_stock`, `search`)
- `POST /api/parts` — Create a part
- `GET /api/parts/{id}` — Get a part (includes computed `total_stock` and `low_stock`)
- `PUT /api/parts/{id}` — Update a part
- `DELETE /api/parts/{id}` — Delete a part

### 3. Stock Locations — hierarchical warehouse structure (2 paths, 5 methods)

Locations form a tree: warehouse → shelf → bin.

- `GET /api/locations` — List locations (optional `parent` filter, `search`)
- `POST /api/locations` — Create a location
- `GET /api/locations/{id}` — Get a location (includes `pathstring`)
- `PUT /api/locations/{id}` — Update a location
- `DELETE /api/locations/{id}` — Delete a location

### 4. Stock Items — physical inventory tracking (2 paths, 5 methods)

Stock items represent physical quantities of parts at specific locations.

- `GET /api/stock` — List stock items (filters: `part`, `location`)
- `POST /api/stock` — Create a stock item
- `GET /api/stock/{id}` — Get a stock item
- `PUT /api/stock/{id}` — Update a stock item
- `DELETE /api/stock/{id}` — Delete a stock item

### 5. BOM (Bill of Materials) — assembly definitions (2 paths, 5 methods)

BOM items define what sub-parts are needed to build one unit of an assembly.

- `GET /api/bom` — List BOM items (filter: `part`)
- `POST /api/bom` — Create a BOM item
- `GET /api/bom/{id}` — Get a BOM item
- `PUT /api/bom/{id}` — Update a BOM item
- `DELETE /api/bom/{id}` — Delete a BOM item

### 6. Suppliers — vendor companies (2 paths, 5 methods)

- `GET /api/suppliers` — List suppliers (`search` filter)
- `POST /api/suppliers` — Create a supplier
- `GET /api/suppliers/{id}` — Get a supplier
- `PUT /api/suppliers/{id}` — Update a supplier
- `DELETE /api/suppliers/{id}` — Delete a supplier

### 7. Supplier Parts — vendor-part links (2 paths, 5 methods)

Link between a supplier and a part, with SKU and pricing info.

- `GET /api/supplier-parts` — List supplier parts (filters: `supplier`, `part`)
- `POST /api/supplier-parts` — Create a supplier part
- `GET /api/supplier-parts/{id}` — Get a supplier part
- `PUT /api/supplier-parts/{id}` — Update a supplier part
- `DELETE /api/supplier-parts/{id}` — Delete a supplier part

### 8. Build Orders — manufacturing orders (3 paths, 6 methods)

Build orders track the process of building assemblies from BOM items.

- `GET /api/builds` — List build orders (filter: `status`, `part`)
- `POST /api/builds` — Create a build order
- `GET /api/builds/{id}` — Get a build order
- `PUT /api/builds/{id}` — Update a build order
- `POST /api/builds/{id}/complete` — Complete a build order
- `POST /api/builds/{id}/cancel` — Cancel a build order

### 9. Purchase Orders — procurement (3 paths, 6 methods)

Purchase orders track ordering parts from suppliers.

- `GET /api/purchase-orders` — List purchase orders (filter: `status`, `supplier`)
- `POST /api/purchase-orders` — Create a purchase order
- `GET /api/purchase-orders/{id}` — Get a purchase order (includes line items)
- `PUT /api/purchase-orders/{id}` — Update a purchase order
- `POST /api/purchase-orders/{id}/issue` — Issue (place) a purchase order
- `POST /api/purchase-orders/{id}/receive` — Receive a purchase order

### 10. Purchase Order Line Items — order details (2 paths, 5 methods)

Individual line items within a purchase order.

- `GET /api/po-lines` — List PO line items (filter: `order`)
- `POST /api/po-lines` — Create a line item
- `GET /api/po-lines/{id}` — Get a line item
- `PUT /api/po-lines/{id}` — Update a line item
- `DELETE /api/po-lines/{id}` — Delete a line item

### 11. Health Check (1 path, 1 method)

- `GET /api/health` — Returns health status (no auth required)

---

**Totals: 23 paths, 48 endpoints across 11 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 23 paths / 48 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Stock tracking**: The `total_stock` field on a Part is always computed as the sum of `quantity` across all StockItems for that part. It is never stored — always calculated on read. The `low_stock` boolean is `true` when `total_stock < minimum_stock` (and `minimum_stock > 0`).

2. **BOM circular reference prevention**: When creating or updating a BOM item, validate that no circular dependency exists. Example: if Part A has Part B in its BOM, then Part B cannot have Part A in its BOM (directly or indirectly). Return `400 Bad Request` with an error message if a cycle would be created.

3. **BOM part must be an assembly**: A BOM item's `part` field (the parent) must reference a Part with `assembly=true`. Return `400` if not.

4. **BOM sub_part cannot equal part**: A part cannot be in its own BOM. Return `400`.

5. **Build order completion** (`POST /api/builds/{id}/complete`):
   - The build order status must be `pending`. Return `400` if already `complete` or `cancelled`.
   - The part must have `assembly=true` and have at least one BOM item.
   - For each BOM item: check that `total_stock(sub_part) >= build_quantity * bom_item.quantity`. If any sub-part has insufficient stock, return `400` with a message indicating which part is short.
   - On success: for each BOM item, subtract `build_quantity * bom_item.quantity` from stock (deduct from existing stock items by reducing their quantity, starting with the lowest-ID stock item first; if a stock item's quantity reaches 0, delete it).
   - Create a new StockItem for the built part with `quantity = build_quantity` (no location, no serial number).
   - Set build order status to `complete` and `completion_date` to current timestamp.

6. **Build order cancellation** (`POST /api/builds/{id}/cancel`):
   - Status must be `pending`. Return `400` if already `complete` or `cancelled`.
   - Set status to `cancelled`.

7. **Purchase order lifecycle**:
   - New POs start with status `pending`.
   - `POST /api/purchase-orders/{id}/issue`: status must be `pending` → sets to `placed`, sets `issue_date`. Return `400` if not pending.
   - `POST /api/purchase-orders/{id}/receive`: status must be `placed` → sets to `received`, sets `complete_date`. For each line item, creates a StockItem with `part=line.part`, `quantity=line.quantity`, and `location` from the request body (required field `location`). Return `400` if not placed or no line items exist.
   - Cannot issue/receive a `cancelled` order.

8. **Category hierarchy — pathstring**: The `pathstring` field on a category is computed as the full path from root, e.g., "Electronics/Resistors/SMD". Use "/" as separator.

9. **Location hierarchy — pathstring**: Same as categories. E.g., "Warehouse A/Shelf 1/Bin 3".

10. **Category deletion**: When a category is deleted, all parts in that category have their `category` set to `null` (they become uncategorized). Sub-categories are also deleted recursively (and their parts also become uncategorized).

11. **Location deletion**: When a location is deleted, all stock items at that location have their `location` set to `null`. Sub-locations are also deleted recursively (and their stock items also have location set to null).

12. **Serial number uniqueness**: Serial numbers must be unique per part. If you try to create a StockItem with a `serial_number` that already exists for the same `part`, return `400`. Null/empty serial numbers are allowed (multiple items without serial numbers are fine).

13. **Part references validation**:
    - `variant_of` must reference a Part with `is_template=true`. Return `400` otherwise.
    - A Part with `is_template=true` cannot itself be a variant (cannot have `variant_of` set).

14. **Supplier part uniqueness**: The combination of (`supplier`, `SKU`) must be unique. Return `400` on duplicate.

15. **Part deletion constraints**: A part cannot be deleted if it has stock items or is referenced in BOM items (as either `part` or `sub_part`) or has active build orders (status=`pending`). Return `400` with an explanation.

16. **Supplier deletion constraints**: A supplier cannot be deleted if it has associated supplier parts. Return `400`.

17. **Pagination**: List endpoints support `limit` (default 50, max 200) and `offset` (default 0) query parameters. Response includes `count` (total matching items), `results` (array of items).
