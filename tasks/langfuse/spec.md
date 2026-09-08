# Langfuse — Backend Implementation Spec

## Overview

Langfuse is an **LLM observability and evaluation platform** (based on [Langfuse](https://github.com/langfuse/langfuse), 10K+ stars). It provides tracing for LLM applications, prompt management, dataset evaluation, and scoring. Teams use it to debug, analyze, and improve their LLM-powered products.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified from the original Langfuse key-pair system):

- `X-Api-Key`: API key identifying the project

Rules:
- The `X-Api-Key` header is required on all endpoints **except** `GET /api/health`.
- If the header is missing on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — the key IS the project identifier. If a project with that key doesn't exist, **auto-create** the project (with the key value as the project name).
- **Data scoping**: All traces, spans, generations, scores, datasets, and prompts are scoped to the project identified by the API key. A project can only see/modify its own data.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (35 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Health — system status (1 endpoint)

- `GET /api/health` — Returns health status (no auth required)

### 2. Traces — LLM call traces (5 endpoints)

Traces represent a single execution/request through your LLM application.

- `POST /api/traces` — Create a trace (body: name, input, output, metadata, userId, sessionId, tags, startTime, endTime)
- `GET /api/traces` — List traces (supports `limit`, `offset`, `userId`, `sessionId`, `tags` filtering)
- `GET /api/traces/{traceId}` — Get a trace with computed stats (totalCost, totalTokens, duration)
- `PATCH /api/traces/{traceId}` — Update a trace
- `DELETE /api/traces/{traceId}` — Delete a trace (cascades to spans, generations, scores)

### 3. Spans — execution segments within traces (4 endpoints)

Spans represent segments of execution within a trace. They form a tree via `parentSpanId`.

- `POST /api/spans` — Create a span (body: traceId required, name, input, output, level, startTime, endTime, parentSpanId, metadata)
- `GET /api/spans` — List spans (supports `traceId` filter)
- `GET /api/spans/{spanId}` — Get a span
- `PATCH /api/spans/{spanId}` — Update a span (endTime, output, level, metadata)

### 4. Generations — LLM call details (4 endpoints)

Generations are special spans that capture LLM-specific data (model, tokens, cost).

- `POST /api/generations` — Create a generation (body: traceId required, name, model, input, output, usage, cost, level, startTime, endTime, parentSpanId, metadata)
- `GET /api/generations` — List generations (supports `traceId` filter)
- `GET /api/generations/{generationId}` — Get a generation
- `PATCH /api/generations/{generationId}` — Update a generation

### 5. Scores — evaluation metrics (4 endpoints)

Scores attach numeric evaluation values to traces.

- `POST /api/scores` — Create a score (body: traceId required, name, value, comment, source)
- `GET /api/scores` — List scores (supports `traceId`, `name`, `source` filter)
- `GET /api/scores/{scoreId}` — Get a score
- `DELETE /api/scores/{scoreId}` — Delete a score

### 6. Datasets — evaluation datasets (4 endpoints)

Datasets group items for batch evaluation.

- `POST /api/datasets` — Create a dataset (body: name, description)
- `GET /api/datasets` — List datasets
- `GET /api/datasets/{datasetName}` — Get a dataset by name
- `DELETE /api/datasets/{datasetName}` — Delete a dataset (cascades to items and runs)

### 7. Dataset Items — evaluation test cases (3 endpoints)

Items within a dataset represent individual test cases.

- `POST /api/dataset-items` — Create a dataset item (body: datasetName, input, expectedOutput, metadata)
- `GET /api/dataset-items/{itemId}` — Get a dataset item
- `DELETE /api/dataset-items/{itemId}` — Delete a dataset item

### 8. Dataset Runs — evaluation executions (3 endpoints)

Runs represent executing a dataset against your application. Run items link dataset items to traces.

- `POST /api/dataset-run-items` — Create a run item (body: datasetItemId, traceId, runName, datasetName) — auto-creates run if needed
- `GET /api/datasets/{datasetName}/runs` — List runs for a dataset
- `GET /api/datasets/{datasetName}/runs/{runName}` — Get run details with items

### 9. Prompts — versioned prompt management (5 endpoints)

Prompts support versioning and labeling (production/staging).

- `POST /api/prompts` — Create a new prompt version (body: name, prompt, labels)
- `GET /api/prompts` — List prompts (unique names with latest version)
- `GET /api/prompts/{promptName}` — Get active (production-labeled) prompt, or latest if no production label; supports `?version=N` and `?label=X` query params
- `GET /api/prompts/{promptName}/versions` — List all versions of a prompt
- `DELETE /api/prompts/{promptName}` — Delete all versions of a prompt

### 10. Sessions — aggregated session view (2 endpoints)

Sessions group traces by sessionId, with aggregated statistics.

- `GET /api/sessions` — List sessions with stats (totalTraces, totalCost, totalTokens, firstTrace, lastTrace)
- `GET /api/sessions/{sessionId}` — Get session detail with trace list

---

**Totals: 35 endpoints across 10 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 35 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create projects**: When a request comes in with `X-Api-Key: somevalue`, if no project with that key exists, automatically create a project with the key as its name.

2. **Trace duration**: When fetching a single trace via `GET /api/traces/{traceId}`, compute `duration` as: `endTime - startTime` in milliseconds. If `endTime` is not set on the trace itself, use the latest `endTime` among all spans and generations belonging to that trace. If neither is available, `duration` is `null`.

3. **Trace total cost**: Computed as the sum of `cost` from all generations belonging to the trace. Returned in `GET /api/traces/{traceId}` response as `totalCost`. If no generations have cost, `totalCost` is `0`.

4. **Trace total tokens**: Computed as the sum of all `usage.totalTokens` from generations belonging to the trace. Returned as `totalTokens`. If no generations exist, `totalTokens` is `0`.

5. **Session aggregation**: `GET /api/sessions` returns sessions derived from all distinct `sessionId` values across traces. Each session includes: `totalTraces` (count), `totalCost` (sum of all trace costs), `totalTokens` (sum of all trace tokens), `firstTrace` (earliest startTime), `lastTrace` (latest startTime).

6. **Prompt versioning**: Each `POST /api/prompts` with the same `name` creates a new version with auto-incremented version number (starting at 1). The version number is per-name within a project.

7. **Active prompt**: The version with the `"production"` label is the active/default one. When `GET /api/prompts/{name}` is called without `?version` or `?label` query param, return the version labeled `"production"`. If no version has `"production"` label, return the highest version number. Only ONE version per prompt name can have the `"production"` label at a time. When a new version is created with `"production"` in its labels, remove `"production"` from all other versions of that name.

8. **Score validation**: `value` must be numeric (int or float). `traceId` must reference an existing trace in the same project. If the trace doesn't exist, return `404`.

9. **Span tree**: Spans form a tree via `parentSpanId`. Root spans have `parentSpanId` as `null`. The `parentSpanId` must reference an existing span in the same trace, or be `null`.

10. **Dataset run items**: A run item links a `datasetItemId` to a `traceId` under a named run. If the run (identified by `runName` + `datasetName`) doesn't exist, it's auto-created. The `datasetItemId` must belong to the dataset identified by `datasetName`.

11. **Client-provided IDs**: For traces, spans, and generations, clients MAY provide an `id` field in the request body (UUID string). If not provided, the server generates one. If a client provides an ID that already exists, return `409 Conflict`.

12. **Cascade deletes**:
    - Deleting a trace deletes all its spans, generations, and scores.
    - Deleting a dataset deletes all its items, runs, and run items.
    - Deleting a prompt name deletes all versions.

13. **Filtering and pagination**: List endpoints support `limit` (default 50, max 100) and `offset` (default 0) for pagination. Specific filters are documented per endpoint in the OpenAPI spec.

14. **Tags**: Trace `tags` is an array of strings. Filtering by tag (`?tags=foo`) returns traces that contain ALL specified tags.

15. **Timestamp handling**: All timestamp fields (`startTime`, `endTime`, `createdAt`, `updatedAt`) use ISO 8601 format. If `startTime` is not provided on trace/span/generation creation, default to current server time.

16. **Level enum**: Span and generation `level` must be one of: `DEBUG`, `DEFAULT`, `WARNING`, `ERROR`. Default is `DEFAULT`.

17. **Usage object**: Generation `usage` is an object with `promptTokens` (int), `completionTokens` (int), `totalTokens` (int). All are optional and default to 0. If `totalTokens` is not provided but `promptTokens` and `completionTokens` are, compute `totalTokens = promptTokens + completionTokens`.
