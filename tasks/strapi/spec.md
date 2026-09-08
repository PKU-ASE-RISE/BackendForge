# Strapi — Headless CMS API

## Overview

Build a headless CMS API inspired by Strapi. The system allows administrators to define dynamic content types (schemas), then create/read/update/delete entries of those content types through a REST API. It supports reusable components, relations between content types, media uploads, localization, role-based access control, API tokens, and webhooks.

## Authentication

All endpoints require an `X-API-Key` header. Missing or invalid key returns `401 Unauthorized`.

Token format: `{role}_{userId}` where role is one of `admin`, `editor`, `author`.

### Roles

| Role | Permissions |
|------|-------------|
| **admin** | Full access: manage content types, fields, components, users, roles, tokens, webhooks, and all entries |
| **editor** | CRUD all entries across all content types. Cannot manage schema (content types, fields, components) |
| **author** | CRUD only their own entries. Cannot manage schema |

## Core Concepts

### Content Types

A content type defines a schema (like a database table). Each content type has:
- `name` (string, unique, lowercase alphanumeric + underscores)
- `displayName` (string)
- `description` (string, optional)
- `fields` (list of field definitions)
- `settings` (object with options like `draftAndPublish`, `localization`)

### Fields

Fields define the structure of a content type. Supported types:
- `text` — string value
- `number` — numeric value (integer or float)
- `boolean` — true/false
- `date` — ISO 8601 date string
- `enum` — one of a set of allowed values
- `relation` — reference to another content type's entry
- `json` — arbitrary JSON data
- `media` — reference to an uploaded media file
- `component` — embedded component data

Field properties:
- `name` (string, required)
- `type` (string, required)
- `required` (boolean, default false)
- `unique` (boolean, default false)
- `default` (any, optional)
- `enumValues` (array of strings, required for enum type)
- `target` (string, content type name — required for relation type)
- `relationType` (oneToOne | oneToMany | manyToMany — required for relation type)
- `component` (string, component name — required for component type)

### Entries

Entries are instances of a content type. Managed at `/content/{contentTypeName}`. Each entry has:
- `id` (auto-generated integer)
- `createdBy` (userId from token)
- `createdAt` (ISO 8601 timestamp)
- `updatedAt` (ISO 8601 timestamp)
- `locale` (string, default "en")
- Dynamic fields as defined by the content type

### Components

Reusable field groups (like a "SEO" component with `metaTitle` + `metaDescription`). Components can be embedded in content types via component-type fields.

### Relations

Content types can reference each other:
- **oneToOne**: entry stores a single reference ID
- **oneToMany**: entry stores an array of reference IDs
- **manyToMany**: bidirectional — both sides store references

When fetching entries, relation fields are **populated** (return nested objects, not just IDs).

### Media Library

Upload files (images, documents), organize them in folders, and attach them to entries via media-type fields.

### Localization

- Default locale is `"en"`
- Content types with `localization` enabled in settings can have localized versions
- Creating a localized version links it to the original entry
- Query entries by locale with `?locale=xx`

### Webhooks

Register URLs to be notified on entry lifecycle events (create, update, delete). Webhooks store the URL and event types; actual HTTP calls are not required for this implementation (just registration and listing).

## API Patterns

### Filtering

GET endpoints for entries support filtering:
```
?filters[field][operator]=value
```
Operators: `eq`, `ne`, `gt`, `lt`, `gte`, `lte`, `contains`, `startsWith`

### Sorting

```
?sort=field:asc
?sort=field:desc
```

### Pagination

```
?page=1&pageSize=10
```

Response includes:
```json
{
  "data": [...],
  "meta": {
    "pagination": {
      "page": 1,
      "pageSize": 10,
      "pageCount": 5,
      "total": 42
    }
  }
}
```

## Error Responses

| Status | Meaning |
|--------|---------|
| 400 | Validation error (missing required field, invalid data) |
| 401 | Missing or invalid API key |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (unique constraint violation, duplicate name) |

Error response body:
```json
{
  "error": {
    "status": <code>,
    "name": "ErrorName",
    "message": "Human-readable message"
  }
}
```

## Storage

- All storage is in-memory (no database required)
- System starts empty — no seed data
- IDs are auto-incrementing integers starting from 1
