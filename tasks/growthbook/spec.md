# GrowthBook — Backend Implementation Spec

## Overview

GrowthBook is a **feature flags and A/B testing platform** (based on [GrowthBook](https://github.com/growthbook/growthbook), 7.7K stars). Organizations create feature flags with rules (force, rollout, experiment) per environment, run experiments with variations, define metrics, and connect client SDKs to evaluate features in real time.

The application manages the full lifecycle of feature flagging: creating features, defining environments, setting up per-environment rules with targeting conditions, running experiments, and providing an SDK endpoint that evaluates features for given user attributes.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-Api-Key`: API key identifying the organization

Rules:
- The `X-Api-Key` header is required on all endpoints **except** `/health`.
- If the header is missing on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — the key IS the organization identifier. If an organization with that key doesn't exist, **auto-create** it (with the key as its name).
- **Data scoping**: All data (projects, features, environments, experiments, metrics, SDK connections) is scoped to the authenticated organization. An organization can only see/modify its own data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (35 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Projects — organizational grouping (2 paths, 5 methods)

Projects group features and experiments for organizational purposes.

- `GET /api/projects` — List all projects
- `POST /api/projects` — Create a project (body: `name`, optional `description`, `settings`)
- `GET /api/projects/{projectId}` — Get a project by ID
- `PUT /api/projects/{projectId}` — Update a project
- `DELETE /api/projects/{projectId}` — Delete a project

### 2. Environments — deployment targets (2 paths, 5 methods)

Environments represent deployment targets (dev, staging, production). Features have per-environment settings.

- `GET /api/environments` — List all environments
- `POST /api/environments` — Create an environment (body: `id`, `name`, `description`)
- `GET /api/environments/{envId}` — Get an environment by ID
- `PUT /api/environments/{envId}` — Update an environment
- `DELETE /api/environments/{envId}` — Delete an environment

### 3. Features — feature flags (3 paths, 6 methods)

Features are the core entity. Each feature has a key, type, default value, and per-environment rules.

- `GET /api/features` — List all features (supports `projectId` filter)
- `POST /api/features` — Create a feature
- `GET /api/features/{featureId}` — Get a feature by ID
- `PUT /api/features/{featureId}` — Update a feature
- `DELETE /api/features/{featureId}` — Delete a feature
- `POST /api/features/{featureId}/toggle/{envId}` — Toggle feature enabled state per environment

### 4. Feature Rules — per-environment rules (2 paths, 4 methods)

Rules define how a feature behaves in a specific environment.

- `GET /api/features/{featureId}/rules/{envId}` — List rules for a feature in an environment
- `POST /api/features/{featureId}/rules/{envId}` — Add a rule
- `PUT /api/features/{featureId}/rules/{envId}/{ruleIndex}` — Update a rule at index
- `DELETE /api/features/{featureId}/rules/{envId}/{ruleIndex}` — Delete a rule at index

### 5. Experiments — A/B tests (2 paths, 5 methods)

Experiments manage A/B tests with variations and traffic allocation.

- `GET /api/experiments` — List all experiments (supports `projectId`, `status` filters)
- `POST /api/experiments` — Create an experiment
- `GET /api/experiments/{experimentId}` — Get an experiment by ID
- `PUT /api/experiments/{experimentId}` — Update an experiment
- `DELETE /api/experiments/{experimentId}` — Delete an experiment

### 6. Metrics — measurement definitions (2 paths, 5 methods)

Metrics define what to measure in experiments.

- `GET /api/metrics` — List all metrics (supports `projectId` filter)
- `POST /api/metrics` — Create a metric
- `GET /api/metrics/{metricId}` — Get a metric by ID
- `PUT /api/metrics/{metricId}` — Update a metric
- `DELETE /api/metrics/{metricId}` — Delete a metric

### 7. SDK Connections — client SDK keys (2 paths, 4 methods)

SDK connections generate keys for client applications to connect.

- `GET /api/sdk-connections` — List all SDK connections
- `POST /api/sdk-connections` — Create an SDK connection
- `GET /api/sdk-connections/{sdkConnectionId}` — Get an SDK connection by ID
- `DELETE /api/sdk-connections/{sdkConnectionId}` — Delete an SDK connection

### 8. SDK Feature Evaluation — resolve features for users (1 path, 1 method)

The SDK endpoint evaluates all features for given user attributes using the rules engine.

- `POST /api/eval/{clientKey}` — Evaluate all features for given user attributes (no auth header required — authenticated by clientKey in URL)

---

**Totals: 16 paths, 35 endpoints across 8 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 16 paths / 35 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create organizations**: When a request comes in with `X-Api-Key: somevalue`, if no organization with that key exists, automatically create it with the key as its name.

2. **Feature key uniqueness**: Feature keys (`id` field) must be unique within an organization. Return `409 Conflict` on duplicate.

3. **Environment ID uniqueness**: Environment IDs must be unique within an organization. Return `409 Conflict` on duplicate.

4. **Feature types**: Features have a `valueType` which must be one of: `boolean`, `string`, `number`, `json`. The `defaultValue` must be a string representation of the value (e.g., `"true"`, `"hello"`, `"42"`, `"{\"key\":\"val\"}"`).

5. **Feature rules evaluation order**: Rules within an environment are evaluated in order (by index, 0-based). First matching rule wins. If no rule matches, the default value is used.

6. **Rule types**:
   - `force`: Always returns the specified value (if condition matches)
   - `rollout`: Returns the value for a percentage of users. Uses hash: `fnv1a_32(featureId + userId) % 10000 < coverage * 10000`
   - `experiment`: Assigns users to variations. Uses hash: `fnv1a_32(experimentKey + userId) % 10000` to determine which variation bucket the user falls into based on cumulative weights.

7. **Targeting conditions**: Rules can have a `condition` field — a JSON object with attribute operators. Supported operators:
   - `$eq` — equals
   - `$ne` — not equals
   - `$gt` — greater than (numeric)
   - `$lt` — less than (numeric)
   - `$gte` — greater than or equal (numeric)
   - `$lte` — less than or equal (numeric)
   - `$in` — value is in array
   - `$nin` — value is not in array
   - `$regex` — value matches regex pattern
   - `$exists` — attribute exists (true) or doesn't exist (false)

   Condition format: `{"attributeName": {"$operator": value}}`. Multiple attributes in condition are ANDed. If condition is empty/null, it always matches.

8. **FNV-1a 32-bit hash**: For rollout and experiment assignment, use the FNV-1a 32-bit hash algorithm:
   - Offset basis: 2166136261
   - Prime: 16777619
   - For each byte of input string: hash = (hash XOR byte) * prime
   - Result is unsigned 32-bit (mask with 0xFFFFFFFF after each multiply)

9. **Experiment variation assignment**: Given variations with weights (summing to 1.0), compute `hashValue = fnv1a_32(experimentKey + userId) % 10000`. Walk through variations accumulating weights * 10000. The user gets the first variation where cumulative weight * 10000 > hashValue.

10. **Feature toggle**: The toggle endpoint flips the `enabled` state for a feature in a specific environment. If the environment doesn't exist in the feature's environments map, return `404`.

11. **Feature deletion protection**: A feature cannot be deleted if it is referenced by a running experiment (status = "running"). Return `409 Conflict`.

12. **Experiment statuses**: Valid statuses are `draft`, `running`, `stopped`. Experiments start as `draft`. Status transitions: `draft` → `running` → `stopped`. Cannot go backwards. Invalid transitions return `400 Bad Request`.

13. **SDK Connection keys**: When an SDK connection is created, generate a unique `clientKey` (random string, at least 20 characters). This key is used in the eval endpoint URL.

14. **SDK Eval endpoint**: `POST /api/eval/{clientKey}` does NOT require the `X-Api-Key` header. It authenticates via the `clientKey` URL parameter. If the clientKey is invalid, return `401`. The request body contains user `attributes`. The response contains evaluated feature values for all features in the SDK connection's environment.

15. **Project deletion**: Deleting a project does NOT delete associated features/experiments. It only removes the project. Features/experiments with that projectId retain the value but are effectively unassigned.

16. **Environment deletion cascade**: Deleting an environment removes all feature rules for that environment across all features, and removes that environment's entry from each feature's `environments` map.

17. **Default environments**: When a feature is created, its `environments` map should contain entries for all existing environments in the organization, each with `enabled: true` and empty rules array.

18. **Metric types**: Valid metric types are `binomial`, `count`, `duration`, `revenue`.
