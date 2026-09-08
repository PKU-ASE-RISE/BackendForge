# Flagsmith — Backend Implementation Spec

## Overview

Flagsmith is a **feature flag and remote config service** (based on [Flagsmith](https://github.com/Flagsmith/flagsmith), 6.3K stars). Organizations manage feature flags across projects and environments, define user segments with attribute-based rules, and resolve personalized flag values for individual identities.

The application supports multi-environment deployments (development, staging, production) where each environment can have different flag states. Flag resolution follows a priority chain: identity override > segment override > environment default.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-Api-Key`: API key identifying the organization

Rules:
- The `X-Api-Key` header is required on every endpoint.
- If the header is missing, return `401 Unauthorized`.
- Trust header values directly — the key IS the organization identifier. No database lookup required to verify.
- **Data scoping**: All data (projects, environments, features, segments, identities, etc.) is scoped to the organization identified by the API key. An organization can only see/modify its own data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (20 paths, 41 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Projects — top-level organizer (2 paths, 5 methods)

Projects group features, environments, and segments together.

- `GET /api/projects` — List all projects for the organization
- `POST /api/projects` — Create a project (body: `name`)
- `GET /api/projects/{project_id}` — Get a single project
- `PUT /api/projects/{project_id}` — Update a project (body: `name`)
- `DELETE /api/projects/{project_id}` — Delete a project (cascades to all environments, features, segments)

### 2. Environments — per-project deployment targets (3 paths, 5 methods)

Each project has multiple environments (e.g., development, staging, production). Each environment gets a unique `apiKey` on creation.

- `GET /api/projects/{project_id}/environments` — List environments in a project
- `POST /api/projects/{project_id}/environments` — Create an environment (body: `name`)
- `GET /api/environments/{environment_id}` — Get environment details
- `PUT /api/environments/{environment_id}` — Update environment (body: `name`)
- `DELETE /api/environments/{environment_id}` — Delete environment (cascades to feature states, identities)

### 3. Features — flag/config definitions (2 paths, 5 methods)

Features are defined at the project level. Each feature has a `type` (FLAG for boolean, CONFIG for remote config values), `initialValue`, and `defaultEnabled` state.

- `GET /api/projects/{project_id}/features` — List features in a project
- `POST /api/projects/{project_id}/features` — Create a feature (body: `name`, `type`, optional `initialValue`, `defaultEnabled`)
- `GET /api/projects/{project_id}/features/{feature_id}` — Get feature details
- `PUT /api/projects/{project_id}/features/{feature_id}` — Update feature (body: `name`, `type`, `initialValue`, `defaultEnabled`)
- `DELETE /api/projects/{project_id}/features/{feature_id}` — Delete feature (removes from all environments)

### 4. Feature States — per-environment flag values (2 paths, 3 methods)

Feature states represent the actual flag values in a specific environment. They are auto-created when a feature or environment is created.

- `GET /api/environments/{environment_id}/featurestates` — List all feature states in environment
- `GET /api/environments/{environment_id}/featurestates/{featurestate_id}` — Get a specific feature state
- `PUT /api/environments/{environment_id}/featurestates/{featurestate_id}` — Update feature state (body: `enabled`, `value`)

### 5. Segments — user segment definitions (2 paths, 5 methods)

Segments define groups of users based on trait rules. Each segment has a `matchType` (ALL = all rules must match, ANY = any rule matches) and a list of `rules`.

- `GET /api/projects/{project_id}/segments` — List segments in a project
- `POST /api/projects/{project_id}/segments` — Create a segment (body: `name`, `matchType`, `rules`)
- `GET /api/projects/{project_id}/segments/{segment_id}` — Get segment details (includes rules)
- `PUT /api/projects/{project_id}/segments/{segment_id}` — Update segment (body: `name`, `matchType`, `rules`)
- `DELETE /api/projects/{project_id}/segments/{segment_id}` — Delete segment (removes overrides)

### 6. Segment Overrides — per-segment flag overrides (2 paths, 4 methods)

Override flag values for identities that match a segment within an environment.

- `GET /api/environments/{environment_id}/segment-overrides` — List all segment overrides in environment
- `POST /api/environments/{environment_id}/segment-overrides` — Create override (body: `featureId`, `segmentId`, `enabled`, `value`, `priority`)
- `PUT /api/environments/{environment_id}/segment-overrides/{override_id}` — Update override
- `DELETE /api/environments/{environment_id}/segment-overrides/{override_id}` — Delete override

### 7. Identities — tracked users/devices (3 paths, 4 methods)

Identities represent individual users or devices tracked within an environment.

- `GET /api/environments/{environment_id}/identities` — List identities in environment
- `POST /api/environments/{environment_id}/identities` — Create identity (body: `identifier`)
- `GET /api/environments/{environment_id}/identities/{identity_id}` — Get identity details
- `DELETE /api/environments/{environment_id}/identities/{identity_id}` — Delete identity (cascades traits, overrides)

### 8. Identity Flags — resolved flag values (1 path, 1 method)

The core flag resolution endpoint. Returns ALL flags for an identity with overrides applied.

- `GET /api/environments/{environment_id}/identities/{identity_id}/flags` — Get resolved flags for identity

### 9. Identity Overrides — per-identity flag overrides (2 paths, 4 methods)

Override flag values for a specific identity.

- `GET /api/environments/{environment_id}/identities/{identity_id}/overrides` — List overrides
- `POST /api/environments/{environment_id}/identities/{identity_id}/overrides` — Create override (body: `featureId`, `enabled`, `value`)
- `PUT /api/environments/{environment_id}/identities/{identity_id}/overrides/{override_id}` — Update override
- `DELETE /api/environments/{environment_id}/identities/{identity_id}/overrides/{override_id}` — Delete override

### 10. Traits — identity attributes (2 paths, 4 methods)

Key-value attributes on identities, used for segment evaluation.

- `GET /api/environments/{environment_id}/identities/{identity_id}/traits` — List traits
- `POST /api/environments/{environment_id}/identities/{identity_id}/traits` — Create/update trait (body: `key`, `value`); upserts by key
- `PUT /api/environments/{environment_id}/identities/{identity_id}/traits/{trait_id}` — Update trait
- `DELETE /api/environments/{environment_id}/identities/{identity_id}/traits/{trait_id}` — Delete trait

### 11. Audit Log — change tracking (1 path, 1 method)

Track all changes to features, environments, and segments.

- `GET /api/projects/{project_id}/audit-log` — List audit log entries (supports `limit` and `offset` pagination)

---

**Totals: 20 paths, 41 endpoints across 11 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 28 paths / 41 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Flag resolution priority**: When resolving flags for an identity via `GET .../identities/{id}/flags`, the value is determined by (highest to lowest priority):
   - Identity override (if one exists for this identity + feature)
   - Segment override (if the identity matches a segment that has an override for this feature; if multiple segments match, use the override with the highest `priority` value)
   - Environment default (the feature state for that environment)

2. **Segment matching**: To determine if an identity matches a segment, evaluate the segment's rules against the identity's traits:
   - If `matchType` is `"ALL"`: ALL rules must match (AND logic)
   - If `matchType` is `"ANY"`: at least one rule must match (OR logic)
   - An identity with no traits never matches a segment that has rules
   - A segment with no rules and matchType `"ALL"` matches ALL identities (vacuous truth)

3. **Rule operators**: Each rule has `property`, `operator`, and `value`. The `property` is matched against the identity's trait with that key. Operators:
   - `EQUAL`: trait value equals rule value (string comparison)
   - `NOT_EQUAL`: trait value does not equal rule value
   - `GREATER_THAN`: trait value > rule value (numeric comparison; if not numeric, string comparison)
   - `LESS_THAN`: trait value < rule value (numeric comparison; if not numeric, string comparison)
   - `CONTAINS`: trait value contains rule value (substring match)
   - `REGEX`: trait value matches rule value as a regex pattern

4. **Auto-create feature states**: When a new feature is created, a feature state must be automatically created for every existing environment in that project (using the feature's `defaultEnabled` and `initialValue`). When a new environment is created, a feature state must be automatically created for every existing feature in that project.

5. **Cascade deletes**:
   - Deleting a project deletes all its environments, features, segments, and related data
   - Deleting a feature removes its feature states, segment overrides, and identity overrides from all environments
   - Deleting an environment removes all its feature states, identities, segment overrides, and identity overrides
   - Deleting a segment removes all its segment overrides
   - Deleting an identity removes all its traits and identity overrides

6. **Unique names**: Feature names must be unique within a project. Environment names must be unique within a project. Segment names must be unique within a project. Project names must be unique within an organization. Return `409 Conflict` on duplicate.

7. **Trait upsert**: `POST .../traits` with a `key` that already exists for that identity updates the existing trait value instead of creating a duplicate. Returns status `200` (not `201`).

8. **Identity override uniqueness**: An identity can have at most one override per feature. Creating a second override for the same feature returns `409 Conflict`.

9. **Segment override uniqueness**: Within an environment, there can be at most one override per (segment, feature) pair. Return `409 Conflict` on duplicate.

10. **Audit log**: Record audit entries when feature states are updated, segment overrides are created/updated/deleted, and identity overrides are created/updated/deleted. Each entry records: `action` (e.g., `"UPDATE_FEATURE_STATE"`), `entityType`, `entityId`, `author` (the organization API key), and `timestamp`.

11. **Feature state value types**: The `value` field in feature states, segment overrides, and identity overrides is stored as a string. It can represent booleans ("true"/"false"), numbers ("42", "3.14"), or arbitrary strings. The resolution endpoint returns it as-is (string).

12. **Environment API key**: Each environment gets a unique auto-generated `apiKey` string (at least 16 characters) on creation. This key is immutable and returned in responses.

13. **Resolved flags response format**: The `GET .../identities/{id}/flags` endpoint returns an array of objects. Each has: `featureId` (int), `featureName` (string), `enabled` (bool), `value` (string), `source` (one of `"DEFAULT"`, `"SEGMENT"`, `"IDENTITY"`).

14. **Audit log pagination**: The audit log endpoint returns `{ "results": [...], "total": int }`. Supports `limit` (default 50) and `offset` (default 0) query parameters.

15. **Not found handling**: Accessing a resource that doesn't exist or belongs to a different organization returns `404 Not Found`.

16. **Missing trait for rule**: If a rule references a trait key that the identity doesn't have, that rule evaluates to false (no match).
