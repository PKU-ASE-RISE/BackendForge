# Twenty CRM — Backend API Specification

## Overview

Twenty is a modern, open-source CRM platform that provides custom objects, sales pipelines, and activity tracking. This task requires building a backend API that powers a workspace-based CRM with people management, company tracking, deal pipelines, activity logging, and extensibility through custom fields.

## Authentication & Authorization

- All endpoints require an `X-API-Key` header
- Missing or empty key returns `401 Unauthorized`
- API key encodes the user's role:
  - Keys starting with `owner_` → Owner role
  - Keys starting with `admin_` → Admin role
  - All other keys → Member role
- All data is scoped to the workspace derived from the API key (the key itself identifies the workspace)

### Role Permissions

| Action | Member | Admin | Owner |
|--------|--------|-------|-------|
| CRUD on people, companies, opportunities, activities, notes | ✓ | ✓ | ✓ |
| Manage tags | ✓ | ✓ | ✓ |
| Create/manage pipelines and stages | ✗ | ✓ | ✓ |
| Create/manage custom fields | ✗ | ✓ | ✓ |
| Create/manage views | ✗ | ✓ | ✓ |
| Manage workspace members | ✗ | ✗ | ✓ |

## Data Models

### People (Contacts)

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| firstName | string | Required |
| lastName | string | Required |
| email | string | Optional |
| phone | string | Optional |
| companyId | string (UUID) | Optional association to a company |
| tags | array of strings | Tag names |
| city | string | Optional |
| jobTitle | string | Optional |
| createdAt | datetime | Auto-generated |
| updatedAt | datetime | Auto-updated |
| (custom fields) | varies | Dynamically added via custom fields |

### Companies

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| name | string | Required |
| domain | string | Optional (e.g., "acme.com") |
| size | string | Optional (e.g., "1-10", "11-50", "51-200", "201-500", "501+") |
| industry | string | Optional |
| annualRevenue | number | Optional |
| totalRevenue | number | Computed: sum of Won opportunity amounts |
| address | string | Optional |
| createdAt | datetime | Auto-generated |
| updatedAt | datetime | Auto-updated |
| (custom fields) | varies | Dynamically added via custom fields |

### Pipelines

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| name | string | Required |
| stages | array | Ordered list of stage objects |
| createdAt | datetime | Auto-generated |
| updatedAt | datetime | Auto-updated |

### Pipeline Stages

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| name | string | Required |
| position | integer | Order within pipeline (0-indexed) |
| color | string | Optional hex color |

### Opportunities (Deals)

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| name | string | Required |
| amount | number | Deal value |
| companyId | string (UUID) | Optional association |
| pipelineId | string (UUID) | Required |
| stageId | string (UUID) | Required (must belong to the pipeline) |
| probability | number | 0-100 percentage |
| closeDate | date string | Expected close date |
| closedAt | datetime | Auto-set when moved to Won/Lost |
| owner | string | Assigned user/member |
| createdAt | datetime | Auto-generated |
| updatedAt | datetime | Auto-updated |
| (custom fields) | varies | Dynamically added via custom fields |

### Activities

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| type | string | Required: "call", "email", "meeting", "task" |
| title | string | Required |
| body | string | Optional description/notes |
| dueDate | datetime | Optional |
| completed | boolean | Default false |
| personId | string (UUID) | Optional link to person |
| companyId | string (UUID) | Optional link to company |
| opportunityId | string (UUID) | Optional link to opportunity |
| createdAt | datetime | Auto-generated |
| updatedAt | datetime | Auto-updated |

### Notes

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| title | string | Optional |
| body | string | Required (rich text content) |
| personId | string (UUID) | Optional link to person |
| companyId | string (UUID) | Optional link to company |
| opportunityId | string (UUID) | Optional link to opportunity |
| createdAt | datetime | Auto-generated |
| updatedAt | datetime | Auto-updated |

### Tags

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| name | string | Required, unique within workspace |
| color | string | Optional hex color |
| createdAt | datetime | Auto-generated |

### Views (Saved Filters)

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| name | string | Required |
| objectType | string | Required: "people", "companies", "opportunities" |
| filters | array | Filter conditions |
| sorts | array | Sort conditions |
| createdAt | datetime | Auto-generated |
| updatedAt | datetime | Auto-updated |

#### Filter Object

| Field | Type | Description |
|-------|------|-------------|
| field | string | Field name to filter on |
| operator | string | "eq", "neq", "gt", "gte", "lt", "lte", "contains", "in" |
| value | any | Filter value |

#### Sort Object

| Field | Type | Description |
|-------|------|-------------|
| field | string | Field name to sort on |
| direction | string | "asc" or "desc" |

### Workspace Members

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| email | string | Required |
| name | string | Required |
| role | string | "owner", "admin", "member" |
| createdAt | datetime | Auto-generated |

### Custom Fields

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Auto-generated |
| name | string | Required (becomes field key in camelCase) |
| label | string | Required (display name) |
| objectType | string | Required: "people", "companies", "opportunities" |
| type | string | Required: "text", "number", "date", "select" |
| options | array of strings | Required for "select" type |
| required | boolean | Default false |
| createdAt | datetime | Auto-generated |

## Business Logic

### Pipeline Stage Movement

- When an opportunity's stage is changed to a stage named "Won":
  - `closedAt` is automatically set to the current timestamp
- When an opportunity's stage is changed to a stage named "Lost":
  - `closedAt` is automatically set to the current timestamp
  - `probability` is automatically set to 0

### Company Revenue Rollup

- A company's `totalRevenue` field is computed as the sum of all opportunity `amount` values where:
  - The opportunity's `companyId` matches the company
  - The opportunity's stage name is "Won"

### Activity Timeline

- `GET /activities?personId={id}` returns all activities linked to that person, ordered by `createdAt` descending
- Activities can be linked to multiple entities simultaneously (e.g., both a person and an opportunity)

### Custom Fields

- When a custom field is added to an object type (e.g., "people"), all subsequent GET responses for that object type include the field with a default value of `null`
- Custom field values are stored per-record and set via PATCH/PUT operations

### Unified Search

- `GET /search?q={query}` searches across people (firstName, lastName, email), companies (name, domain), and opportunities (name)
- Returns results grouped by type

## API Endpoints Summary

### People
- `GET /people` — List people (with pagination, filtering)
- `POST /people` — Create person
- `GET /people/{id}` — Get person
- `PATCH /people/{id}` — Update person
- `DELETE /people/{id}` — Delete person
- `GET /people/{id}/activities` — Get activities for person
- `GET /people/{id}/notes` — Get notes for person

### Companies
- `GET /companies` — List companies
- `POST /companies` — Create company
- `GET /companies/{id}` — Get company (includes totalRevenue)
- `PATCH /companies/{id}` — Update company
- `DELETE /companies/{id}` — Delete company
- `GET /companies/{id}/people` — Get people at company
- `GET /companies/{id}/activities` — Get activities for company
- `GET /companies/{id}/notes` — Get notes for company

### Pipelines
- `GET /pipelines` — List pipelines (Admin+)
- `POST /pipelines` — Create pipeline (Admin+)
- `GET /pipelines/{id}` — Get pipeline with stages (Admin+)
- `PATCH /pipelines/{id}` — Update pipeline (Admin+)
- `DELETE /pipelines/{id}` — Delete pipeline (Admin+)
- `POST /pipelines/{id}/stages` — Add stage (Admin+)
- `PATCH /pipelines/{id}/stages/{stageId}` — Update stage (Admin+)
- `DELETE /pipelines/{id}/stages/{stageId}` — Delete stage (Admin+)

### Opportunities
- `GET /opportunities` — List opportunities
- `POST /opportunities` — Create opportunity
- `GET /opportunities/{id}` — Get opportunity
- `PATCH /opportunities/{id}` — Update opportunity (stage changes trigger business logic)
- `DELETE /opportunities/{id}` — Delete opportunity
- `GET /opportunities/{id}/activities` — Get activities for opportunity
- `GET /opportunities/{id}/notes` — Get notes for opportunity

### Activities
- `GET /activities` — List activities (filterable by personId, companyId, opportunityId)
- `POST /activities` — Create activity
- `GET /activities/{id}` — Get activity
- `PATCH /activities/{id}` — Update activity
- `DELETE /activities/{id}` — Delete activity

### Notes
- `GET /notes` — List notes (filterable by personId, companyId, opportunityId)
- `POST /notes` — Create note
- `GET /notes/{id}` — Get note
- `PATCH /notes/{id}` — Update note
- `DELETE /notes/{id}` — Delete note

### Tags
- `GET /tags` — List tags
- `POST /tags` — Create tag
- `PATCH /tags/{id}` — Update tag
- `DELETE /tags/{id}` — Delete tag

### Views (Admin+)
- `GET /views` — List views
- `POST /views` — Create view
- `GET /views/{id}` — Get view
- `GET /views/{id}/results` — Execute view (apply filters/sorts)
- `PATCH /views/{id}` — Update view
- `DELETE /views/{id}` — Delete view

### Custom Fields (Admin+)
- `GET /custom-fields` — List custom fields
- `POST /custom-fields` — Create custom field
- `DELETE /custom-fields/{id}` — Delete custom field

### Workspace Members (Owner only)
- `GET /members` — List members
- `POST /members` — Add member
- `PATCH /members/{id}` — Update member role
- `DELETE /members/{id}` — Remove member

### Search
- `GET /search?q={query}` — Unified search

## Pagination

List endpoints support:
- `limit` — Number of results (default 20, max 100)
- `offset` — Offset for pagination (default 0)

Response format for lists:
```json
{
  "data": [...],
  "totalCount": 42,
  "limit": 20,
  "offset": 0
}
```

## Error Responses

Standard error format:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Person not found"
  }
}
```

HTTP Status codes:
- 200: Success
- 201: Created
- 204: Deleted (no content)
- 400: Bad request (validation)
- 401: Unauthorized
- 403: Forbidden (insufficient role)
- 404: Not found
- 409: Conflict (e.g., duplicate tag name)
