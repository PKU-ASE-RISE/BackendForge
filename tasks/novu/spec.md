# Novu — Notification Infrastructure Platform

## Overview

Build a notification infrastructure API that allows developers to manage multi-channel notification workflows. The system supports defining notification workflows with multiple steps (email, SMS, push, in-app, chat), managing subscribers and their preferences, grouping subscribers into topics for broadcast, and triggering notifications with payload data.

## External Services

A delivery service is available through the `DELIVERY_SERVICE_URL` environment variable. The evaluator sets this variable to the reachable service URL; use `http://localhost:9998` as the local-development fallback. The service handles actual notification delivery:

- `POST /v1/send/email` — Send an email notification
  - Body: `{"to": "email@example.com", "subject": "...", "body": "...", "from": "sender@example.com"}`
  - Returns: `{"messageId": "uuid", "status": "sent"}` (or `"failed"` if `to` contains "fail")

- `POST /v1/send/sms` — Send an SMS notification
  - Body: `{"to": "+1234567890", "body": "...", "from": "+0987654321"}`
  - Returns: `{"messageId": "uuid", "status": "sent"}` (or `"failed"` if `to` contains "fail")

- `POST /v1/send/push` — Send a push notification
  - Body: `{"token": "device-token", "title": "...", "body": "...", "data": {}}`
  - Returns: `{"messageId": "uuid", "status": "sent"}` (or `"failed"` if `token` contains "fail")

- `GET /v1/status/{messageId}` — Check delivery status
  - Returns: `{"messageId": "...", "status": "sent|delivered|failed"}`

- `GET /v1/logs` — List all sent messages (for verification)
  - Returns: `{"messages": [...]}`

## Authentication

All API requests must include an `X-API-Key` header. Requests without a valid API key receive a `401 Unauthorized` response.

Each API key belongs to an organization. All data is scoped to the organization that owns the API key — organizations cannot see each other's data.

For this implementation, use a hardcoded API key: `test-api-key-1` belonging to organization `org_1`.

## Core Concepts

### Workflows
A workflow defines a notification template — a sequence of steps that execute when triggered. Each workflow has:
- A unique identifier and name
- An optional notification group
- An active/inactive status
- A list of ordered steps
- Trigger identifier (used when firing the workflow)

### Steps
Each step in a workflow represents a notification action:
- Channel type: `email`, `sms`, `push`, `in_app`, `chat`
- Content template with variable substitution (use `{{variableName}}` syntax)
- Order/priority within the workflow
- Active/inactive status
- Optional filters (conditions for step execution)

### Subscribers
Recipients of notifications:
- Unique subscriberId (external identifier)
- Contact details: email, phone, push tokens
- Metadata/custom data
- Channel preferences (opt-in/opt-out per channel globally or per workflow)

### Topics
Groups of subscribers for broadcast notifications:
- Unique topic key
- Name
- List of subscriber memberships

### Triggers
Fire a workflow for one or more subscribers:
- Reference workflow by trigger identifier
- Provide subscriber(s) or topic
- Pass payload data for template variable substitution
- Creates activity/event records tracking delivery

### Activity Feed
Log of all notification events:
- Which workflow was triggered
- For which subscriber
- Delivery status per step (pending, sent, delivered, failed)
- Timestamps

### Notification Groups
Organizational grouping for workflows (e.g., "Marketing", "Transactional").

### Environments
Logical separation (e.g., "Development", "Production"). Each environment can have different integration configurations.

### Integrations
Configure delivery providers per channel. An integration connects to the delivery service with provider-specific credentials.

## Trigger Execution Logic

When a workflow is triggered for a subscriber:
1. Check workflow is active
2. For each step in order:
   a. Check step is active
   b. Check subscriber has not opted out of this channel (check both global and workflow-specific preferences)
   c. Resolve template variables from trigger payload
   d. Call delivery service with resolved content
   e. Record activity with delivery status
3. If subscriber has opted out of a channel, skip that step (mark as "skipped" in activity)
4. If delivery fails, record failed status but continue to next step

## Template Variable Substitution

Content templates use `{{variableName}}` syntax. When triggered with payload `{"name": "John"}`, the template `"Hello {{name}}"` becomes `"Hello John"`.

## Data Storage

Storage starts empty — no seed data. All entities are created via the API.

## Technical Requirements

- All field names use camelCase
- IDs are server-generated UUIDs
- Timestamps are ISO 8601 format
- List endpoints support pagination with `page` (default 0) and `limit` (default 10) query parameters
- List responses include `{"data": [...], "page": N, "limit": N, "total": N}`
- Create/update responses return the full entity
- Delete returns 204 No Content
- Not found returns 404
- Validation errors return 422
