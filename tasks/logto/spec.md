# Logto — Backend Implementation Spec

## Overview

Logto is a **user authentication & authorization management platform** (inspired by [Logto](https://github.com/logto-io/logto), 20K+ stars). It provides a management API for identity infrastructure: users, applications, API resources, permissions (scopes), roles, organizations, and audit logging. This is a simplified REST API — no actual OAuth/OIDC protocol flows.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified management API key):

- `X-Api-Key`: Management API key

Rules:
- The `X-Api-Key` header is required on **all** endpoints.
- If the header is missing or empty, return `401 Unauthorized` with body `{"message": "Unauthorized"}`.
- Trust header values directly — any non-empty value is accepted as a valid management API key. No database lookup needed.
- There is no data isolation by API key — all API keys see the same data. This is a management API.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (44 endpoints across 28 paths). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Users — identity management (5 endpoints)

- `GET /api/users` — List users (supports `page`, `page_size`, `search` query params)
- `POST /api/users` — Create a user (body: `username`, `email`, `name`, `avatar`, `customData`, `isSuspended`)
- `GET /api/users/{userId}` — Get user by ID
- `PATCH /api/users/{userId}` — Update user fields
- `DELETE /api/users/{userId}` — Delete user (cascades: removes role assignments, org memberships)

### 2. Applications — OAuth app registry (5 endpoints)

- `GET /api/applications` — List applications (supports `page`, `page_size`, `type` filter)
- `POST /api/applications` — Create application (body: `name`, `description`, `type`). `clientId` (UUID) and `clientSecret` (32-char random) auto-generated.
- `GET /api/applications/{applicationId}` — Get application by ID
- `PATCH /api/applications/{applicationId}` — Update application
- `DELETE /api/applications/{applicationId}` — Delete application

### 3. Resources — API resource registry (5 endpoints)

- `GET /api/resources` — List resources
- `POST /api/resources` — Create resource (body: `name`, `indicator`)
- `GET /api/resources/{resourceId}` — Get resource by ID (includes scopes)
- `PATCH /api/resources/{resourceId}` — Update resource
- `DELETE /api/resources/{resourceId}` — Delete resource (cascades: deletes scopes, removes from roles)

### 4. Scopes — permissions within resources (4 endpoints)

- `GET /api/resources/{resourceId}/scopes` — List scopes for a resource
- `POST /api/resources/{resourceId}/scopes` — Create scope within resource
- `PATCH /api/resources/{resourceId}/scopes/{scopeId}` — Update scope
- `DELETE /api/resources/{resourceId}/scopes/{scopeId}` — Delete scope (removes from roles)

### 5. Roles — RBAC management (5 endpoints)

- `GET /api/roles` — List roles (supports `page`, `page_size`, `type` filter, `search`)
- `POST /api/roles` — Create role (body: `name`, `description`, `type`)
- `GET /api/roles/{roleId}` — Get role by ID
- `PATCH /api/roles/{roleId}` — Update role
- `DELETE /api/roles/{roleId}` — Delete role (cascades: removes assignments)

### 6. Role-User Assignment (3 endpoints)

- `GET /api/roles/{roleId}/users` — List users assigned to role
- `POST /api/roles/{roleId}/users` — Assign users to role (body: `userIds` array)
- `DELETE /api/roles/{roleId}/users/{userId}` — Remove user from role

### 7. Role-Scope Assignment (3 endpoints)

- `GET /api/roles/{roleId}/scopes` — List scopes assigned to role
- `POST /api/roles/{roleId}/scopes` — Assign scopes to role (body: `scopeIds` array)
- `DELETE /api/roles/{roleId}/scopes/{scopeId}` — Remove scope from role

### 8. User Roles & Permissions (2 endpoints)

- `GET /api/users/{userId}/roles` — List roles assigned to user
- `GET /api/users/{userId}/permissions` — Get effective permissions (union of scopes from all assigned roles)

### 9. Organizations — multi-tenancy (5 endpoints)

- `GET /api/organizations` — List organizations
- `POST /api/organizations` — Create organization (body: `name`, `description`)
- `GET /api/organizations/{organizationId}` — Get organization by ID
- `PATCH /api/organizations/{organizationId}` — Update organization
- `DELETE /api/organizations/{organizationId}` — Delete organization (cascades: removes memberships)

### 10. Organization Members (3 endpoints)

- `GET /api/organizations/{organizationId}/members` — List members of organization
- `POST /api/organizations/{organizationId}/members` — Add members (body: `userIds` array)
- `DELETE /api/organizations/{organizationId}/members/{userId}` — Remove member

### 11. Sign-in Experience (2 endpoints)

- `GET /api/sign-in-exp` — Get sign-in experience settings
- `PATCH /api/sign-in-exp` — Update sign-in experience settings

### 12. Audit Logs (2 endpoints)

- `GET /api/logs` — List audit logs (supports `page`, `page_size`, `userId`, `type` filter)
- `GET /api/logs/{logId}` — Get single audit log

---

**Totals: 28 paths, 44 endpoints across 12 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 28 paths / 44 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup (sign-in experience returns defaults)

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Permission resolution**: A user's effective permissions (`GET /api/users/{userId}/permissions`) = the union of all scopes from all roles assigned to that user. Each permission in the response includes `resourceId`, `resourceIndicator`, `scopeId`, `scopeName`, and `scopeDescription`.

2. **Suspended users**: If a user's `isSuspended` is `true`, their effective permissions resolve to an empty array `[]` — even if roles are assigned.

3. **Role types**: Roles have a `type` field: `"User"` or `"MachineToMachine"`. Both types can be assigned scopes. Only `"User"` type roles can be assigned to users via `/api/roles/{roleId}/users`. Attempting to assign a `"MachineToMachine"` role to a user returns `422`.

4. **Client credentials auto-generation**: When creating an application, `clientId` is auto-generated as a UUID and `clientSecret` is auto-generated as a random 32-character alphanumeric string. These are immutable — updates cannot change them.

5. **Application types**: Must be one of: `"SPA"`, `"Traditional"`, `"MachineToMachine"`. Reject others with `422`.

6. **Scope uniqueness**: Scope `name` must be unique within a resource. Creating a duplicate returns `409 Conflict`.

7. **Role name uniqueness**: Role `name` must be globally unique. Creating a duplicate returns `409 Conflict`.

8. **Resource indicator uniqueness**: Resource `indicator` must be globally unique. Creating a duplicate returns `409 Conflict`.

9. **Username uniqueness**: `username` must be globally unique. Creating a duplicate returns `409 Conflict`.

10. **Audit log auto-generation**: The following actions automatically create audit log entries:
    - User created → type `"User.Created"`
    - User updated → type `"User.Updated"`
    - User deleted → type `"User.Deleted"`
    - Role assignment added → type `"Role.User.Assigned"`
    - Role assignment removed → type `"Role.User.Unassigned"`

    Each log entry has: `id`, `type`, `userId` (the affected user, or null), `payload` (JSON with action details), `createdAt`.

11. **Organization membership**: Adding a user to an org is idempotent — adding an already-existing member does not error, just succeeds silently. Removing a non-member returns `404`.

12. **Cascade deletes**:
    - Deleting a user removes their role assignments and org memberships.
    - Deleting a role removes all user-role and role-scope assignments.
    - Deleting a resource removes all its scopes and their role-scope assignments.
    - Deleting a scope removes its role-scope assignments.
    - Deleting an organization removes all its memberships.

13. **Sign-in experience defaults**: On first `GET /api/sign-in-exp` (before any PATCH), return default values: `{"id": "default", "branding": {"logoUrl": "", "darkLogoUrl": "", "primaryColor": "#6C63FF", "darkMode": false}}`.

14. **Pagination**: List endpoints support `page` (1-indexed, default 1) and `page_size` (default 20, max 100). Response includes `totalCount` in a custom header `X-Total-Count`. The response body is the array of items directly.

15. **Search**: `GET /api/users` supports `search` param — matches against `username`, `email`, or `name` (case-insensitive substring). `GET /api/roles` supports `search` — matches against `name`.

16. **IDs**: All entity IDs are auto-generated strings (UUIDs or similar unique identifiers). The implementation must generate them — clients never provide IDs.

17. **Timestamps**: `createdAt` fields use ISO 8601 format (e.g., `"2024-01-15T10:30:00Z"`).

18. **customData**: The `customData` field on users is arbitrary JSON. It defaults to `{}` (empty object) if not provided. Updates merge at the top level (PATCH replaces the entire `customData` if provided in the body).
