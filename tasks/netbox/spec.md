# NetBox — Backend Implementation Spec

## Overview

NetBox is a **network/datacenter infrastructure management (CMDB) tool** (based on [NetBox](https://github.com/netbox-community/netbox), 16K+ stars). It models physical and logical network infrastructure: sites, racks, devices, cabling, IP addresses, VLANs, and more.

A typical deployment manages hundreds of devices across multiple sites, tracking rack space utilization, IP address allocation, and physical connectivity.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-Api-Key`: API key identifying the caller

Rules:
- The `X-Api-Key` header is required on **all** endpoints.
- If the header is missing or empty, return `401 Unauthorized`.
- Trust header values directly — no database lookup needed. Any non-empty value is accepted.
- **Data scoping**: All data is global. There is no per-user data isolation. The API key is purely for authentication gating.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (50 endpoints across 12 resource types). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Regions — geographic hierarchy (4 endpoints)

Regions represent geographic areas and can be nested (parent/child hierarchy).

- `GET /api/dcim/regions/` — List all regions
- `POST /api/dcim/regions/` — Create a region (body: `name`, optional `parent`)
- `GET /api/dcim/regions/{id}/` — Get a region by ID
- `DELETE /api/dcim/regions/{id}/` — Delete a region

### 2. Sites — physical locations (5 endpoints)

Sites are physical locations (data centers, offices) that belong to a region.

- `GET /api/dcim/sites/` — List all sites
- `POST /api/dcim/sites/` — Create a site
- `GET /api/dcim/sites/{id}/` — Get a site by ID
- `PUT /api/dcim/sites/{id}/` — Update a site
- `DELETE /api/dcim/sites/{id}/` — Delete a site

### 3. Manufacturers — equipment vendors (4 endpoints)

- `GET /api/dcim/manufacturers/` — List all manufacturers
- `POST /api/dcim/manufacturers/` — Create a manufacturer
- `GET /api/dcim/manufacturers/{id}/` — Get by ID
- `DELETE /api/dcim/manufacturers/{id}/` — Delete

### 4. Device Types — hardware models (4 endpoints)

- `GET /api/dcim/device-types/` — List all device types
- `POST /api/dcim/device-types/` — Create a device type
- `GET /api/dcim/device-types/{id}/` — Get by ID
- `DELETE /api/dcim/device-types/{id}/` — Delete

### 5. Device Roles — functional roles (4 endpoints)

- `GET /api/dcim/device-roles/` — List all device roles
- `POST /api/dcim/device-roles/` — Create a device role
- `GET /api/dcim/device-roles/{id}/` — Get by ID
- `DELETE /api/dcim/device-roles/{id}/` — Delete

### 6. Racks — equipment racks (5 endpoints)

- `GET /api/dcim/racks/` — List all racks
- `POST /api/dcim/racks/` — Create a rack
- `GET /api/dcim/racks/{id}/` — Get a rack (includes computed `utilization` percentage)
- `PUT /api/dcim/racks/{id}/` — Update a rack
- `DELETE /api/dcim/racks/{id}/` — Delete a rack

### 7. Devices — network/server equipment (5 endpoints)

- `GET /api/dcim/devices/` — List all devices
- `POST /api/dcim/devices/` — Create a device
- `GET /api/dcim/devices/{id}/` — Get a device by ID
- `PUT /api/dcim/devices/{id}/` — Update a device
- `DELETE /api/dcim/devices/{id}/` — Delete a device

### 8. Interfaces — device network ports (4 endpoints)

- `GET /api/dcim/interfaces/` — List all interfaces (supports `?device_id=` filter)
- `POST /api/dcim/interfaces/` — Create an interface
- `GET /api/dcim/interfaces/{id}/` — Get by ID
- `DELETE /api/dcim/interfaces/{id}/` — Delete

### 9. IP Addresses — IP address management (5 endpoints)

- `GET /api/ipam/ip-addresses/` — List all IP addresses
- `POST /api/ipam/ip-addresses/` — Create an IP address
- `GET /api/ipam/ip-addresses/{id}/` — Get by ID
- `PUT /api/ipam/ip-addresses/{id}/` — Update an IP address
- `DELETE /api/ipam/ip-addresses/{id}/` — Delete

### 10. Prefixes — IP network prefixes (4 endpoints)

- `GET /api/ipam/prefixes/` — List all prefixes
- `POST /api/ipam/prefixes/` — Create a prefix
- `GET /api/ipam/prefixes/{id}/` — Get by ID (includes list of IP addresses within)
- `DELETE /api/ipam/prefixes/{id}/` — Delete

### 11. VLANs — virtual LANs (5 endpoints)

- `GET /api/ipam/vlans/` — List all VLANs
- `POST /api/ipam/vlans/` — Create a VLAN
- `GET /api/ipam/vlans/{id}/` — Get by ID
- `PUT /api/ipam/vlans/{id}/` — Update a VLAN
- `DELETE /api/ipam/vlans/{id}/` — Delete

### 12. Cables — physical connections (4 endpoints)

- `GET /api/dcim/cables/` — List all cables
- `POST /api/dcim/cables/` — Create a cable (connects two interfaces)
- `GET /api/dcim/cables/{id}/` — Get by ID
- `DELETE /api/dcim/cables/{id}/` — Delete

### 13. Tenants — organizational grouping (4 endpoints)

- `GET /api/tenancy/tenants/` — List all tenants
- `POST /api/tenancy/tenants/` — Create a tenant
- `GET /api/tenancy/tenants/{id}/` — Get by ID
- `DELETE /api/tenancy/tenants/{id}/` — Delete

---

**Totals: 57 endpoints across 13 resource groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Slug auto-generation**: For resources with a `slug` field (Regions, Sites, Manufacturers, Device Types, Device Roles, Tenants), if `slug` is not provided in the request body, auto-generate it from `name` (or `model` for device types): lowercase, replace spaces/special chars with hyphens, strip leading/trailing hyphens. Slugs must be unique per resource type. If a provided or generated slug conflicts, return `400 Bad Request`.

2. **Rack space validation**: When a device is placed in a rack (`rack` and `position` are both set), the device occupies rack units from `position` to `position + device_type.u_height - 1`. These units must not overlap with any other device in the same rack. Also: `position >= 1` and `position + u_height - 1 <= rack.u_height`. Violation returns `400 Bad Request`.

3. **IP address uniqueness**: The `address` field (in CIDR notation, e.g. "192.168.1.1/24") must be unique. Attempting to create or update to a duplicate returns `400 Bad Request`.

4. **VLAN vid range**: The `vid` field must be between 1 and 4094 inclusive. Out-of-range returns `400 Bad Request`.

5. **Cable endpoint validation**: A cable connects exactly two interfaces (`interface_a` and `interface_b`). Both must exist, must be different interfaces, and neither can already be connected to another cable. Violation returns `400 Bad Request`.

6. **Region hierarchy**: Regions can have a `parent` (FK to another region). A region cannot be its own parent. Circular references should be rejected with `400 Bad Request`.

7. **Rack utilization**: When retrieving a rack via GET, include a computed field `utilization` (integer, 0-100) representing the percentage of occupied rack units: `floor(occupied_units / u_height * 100)`. Occupied units = sum of u_height of all devices with `position` set in that rack.

8. **Prefix contains IPs**: When retrieving a prefix via GET, include a computed field `ip_addresses` listing all IP address objects whose address falls within the prefix's CIDR range.

9. **Foreign key validation**: When creating/updating resources with foreign key references (e.g., device references a rack_id), the referenced resource must exist. If not, return `400 Bad Request`.

10. **Cascade behavior on delete**: Deleting a site does NOT cascade to racks/devices (return `400` if site has racks). Deleting a rack does NOT cascade to devices (return `400` if rack has devices). Deleting a device DOES cascade to its interfaces. Deleting an interface removes any cable attached to it.

11. **Status field enums**:
    - Sites: `active`, `planned`, `decommissioning`
    - Racks: `active`, `planned`, `reserved`, `deprecated`
    - Devices: `active`, `planned`, `staged`, `offline`, `decommissioned`
    - IP Addresses: `active`, `reserved`, `deprecated`, `dhcp`
    - Prefixes: `active`, `reserved`, `deprecated`, `container`
    - VLANs: `active`, `reserved`, `deprecated`
    - Cables: `connected`, `planned`, `decommissioning`

12. **List endpoint filtering**: All list endpoints support optional query parameter filtering by key fields (documented in openapi.yaml). For example, `GET /api/dcim/devices/?site_id=1` returns only devices at that site.

13. **Response format**: All successful creates return `201 Created`. All successful updates return `200 OK`. All successful deletes return `204 No Content`. All list endpoints return a JSON object with `count` (total number) and `results` (array of items).
