# Hoppscotch API Development Platform

## Overview

Hoppscotch is an API development tool that allows developers to organize, test, and collaborate on HTTP API requests. It provides collections for organizing requests, environments for managing variables, team collaboration features, and request history tracking.

## Authentication

All endpoints require an `X-API-Key` header containing the user ID. Missing or empty key returns 401 Unauthorized.

```
X-API-Key: user1
```

## Core Concepts

### Collections
Collections organize API requests into logical groups. Collections support nesting — a collection can have a parent collection, creating a tree structure. Each collection has:
- `id`: unique identifier
- `name`: display name
- `description`: optional description
- `parentId`: optional parent collection ID (null for root collections)
- `order`: integer for custom sorting within the same parent
- `createdAt`, `updatedAt`: timestamps

### Requests
Saved HTTP requests within collections. Each request stores:
- `id`: unique identifier
- `collectionId`: the collection this request belongs to
- `name`: display name
- `method`: HTTP method (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS)
- `url`: the request URL (may contain `{{variable}}` references)
- `headers`: array of {key, value, active} objects
- `params`: array of {key, value, active} query parameters
- `body`: request body object with `contentType` and `content`
- `auth`: authentication config with `type` and type-specific fields
- `preRequestScript`: optional script code (stored, not executed)
- `testScript`: optional test assertions code (stored, not executed)
- `order`: integer for custom sorting within collection
- `createdAt`, `updatedAt`: timestamps

### Environments
Key-value variable sets used across requests. Variables like `{{baseUrl}}` in request URLs/headers reference environment values. Each environment has:
- `id`: unique identifier
- `name`: display name
- `variables`: array of {key, value, active} objects
- `global`: boolean (true = global environment, only one allowed per user)
- `createdAt`, `updatedAt`: timestamps

### History
Auto-saved request execution records. Each entry has:
- `id`: unique identifier
- `method`: HTTP method used
- `url`: the URL called
- `statusCode`: response status code
- `responseTime`: response time in milliseconds
- `requestHeaders`: headers sent
- `requestBody`: body sent
- `responseHeaders`: headers received
- `responseBody`: body received (truncated if large)
- `executedAt`: timestamp of execution

### Teams
Team workspaces for collaboration. Teams have:
- `id`: unique identifier
- `name`: team name
- `description`: optional description
- `members`: list of members with roles
- `createdAt`, `updatedAt`: timestamps

### Team Roles
- **Owner**: full access — manage members, delete team, CRUD collections/requests/environments
- **Editor**: CRUD on team collections, requests, and environments
- **Viewer**: read-only access to team collections, requests, and environments

### Team Invitations
Inviting a user to a team creates a pending invitation. The invited user must accept it to become a member.

## API Endpoints

### Personal Collections
- `POST /collections` — Create a collection
- `GET /collections` — List personal collections (filter by parentId)
- `GET /collections/{id}` — Get collection details
- `PUT /collections/{id}` — Update collection
- `DELETE /collections/{id}` — Delete collection (and all children + requests)
- `POST /collections/{id}/duplicate` — Duplicate collection with all nested content
- `PATCH /collections/{id}/move` — Move collection to new parent

### Personal Requests
- `POST /requests` — Create a request in a collection
- `GET /requests` — List requests (filter by collectionId)
- `GET /requests/{id}` — Get request details
- `PUT /requests/{id}` — Update request
- `DELETE /requests/{id}` — Delete request
- `POST /requests/{id}/duplicate` — Duplicate request
- `PATCH /requests/{id}/move` — Move request to another collection

### Environments
- `POST /environments` — Create an environment
- `GET /environments` — List environments
- `GET /environments/{id}` — Get environment details
- `PUT /environments/{id}` — Update environment (including variables)
- `DELETE /environments/{id}` — Delete environment

### History
- `POST /history` — Record a history entry
- `GET /history` — List history (pagination, newest first)
- `GET /history/{id}` — Get history entry details
- `DELETE /history` — Clear all history for user

### Teams
- `POST /teams` — Create a team
- `GET /teams` — List user's teams
- `GET /teams/{id}` — Get team details
- `PUT /teams/{id}` — Update team (owner only)
- `DELETE /teams/{id}` — Delete team (owner only)

### Team Members & Invitations
- `GET /teams/{teamId}/members` — List team members
- `POST /teams/{teamId}/invitations` — Invite a user (owner only)
- `GET /teams/{teamId}/invitations` — List pending invitations
- `POST /invitations/{id}/accept` — Accept an invitation

### Team Collections
- `POST /teams/{teamId}/collections` — Create team collection (editor/owner)
- `GET /teams/{teamId}/collections` — List team collections (any member)
- `GET /teams/{teamId}/collections/{id}` — Get team collection (any member)
- `PUT /teams/{teamId}/collections/{id}` — Update team collection (editor/owner)
- `DELETE /teams/{teamId}/collections/{id}` — Delete team collection (editor/owner)
- `POST /teams/{teamId}/collections/{id}/duplicate` — Duplicate team collection (editor/owner)

### Team Requests
- `POST /teams/{teamId}/requests` — Create request in team collection (editor/owner)
- `GET /teams/{teamId}/requests` — List team requests (any member, filter by collectionId)
- `GET /teams/{teamId}/requests/{id}` — Get team request (any member)
- `PUT /teams/{teamId}/requests/{id}` — Update team request (editor/owner)
- `DELETE /teams/{teamId}/requests/{id}` — Delete team request (editor/owner)

### Team Environments
- `POST /teams/{teamId}/environments` — Create team environment (editor/owner)
- `GET /teams/{teamId}/environments` — List team environments (any member)
- `PUT /teams/{teamId}/environments/{id}` — Update team environment (editor/owner)
- `DELETE /teams/{teamId}/environments/{id}` — Delete team environment (editor/owner)

### Import/Export
- `POST /import/postman` — Import a Postman collection JSON
- `POST /collections/{id}/export` — Export a collection as JSON

## Business Logic Details

### Collection Duplication
When duplicating a collection:
1. Create a copy of the collection with " (copy)" appended to the name
2. Recursively duplicate all child collections
3. Duplicate all requests within each duplicated collection
4. Maintain the same hierarchy structure
5. Return the new root collection

### Collection Deletion
Deleting a collection cascades:
- All child collections are deleted
- All requests within deleted collections are deleted

### Moving Collections
Moving a collection changes its `parentId`. A collection cannot be moved to be a child of itself or any of its descendants (cycle detection).

### Import Postman Format
Accepts Postman Collection v2.1 JSON format:
```json
{
  "info": { "name": "Collection Name", "description": "..." },
  "item": [
    {
      "name": "Folder",
      "item": [
        {
          "name": "Request",
          "request": {
            "method": "GET",
            "url": { "raw": "https://api.example.com/users" },
            "header": [{"key": "Content-Type", "value": "application/json"}],
            "body": { "mode": "raw", "raw": "{}" }
          }
        }
      ]
    }
  ]
}
```

### Export Format
Exports a collection as JSON including all nested collections and requests in a hierarchical structure.

### History Pagination
History list supports `page` (default 1) and `perPage` (default 20, max 100) query parameters. Results ordered by `executedAt` descending (newest first).

### Ordering
Collections and requests have an `order` field (integer). When listing, items are sorted by `order` ascending. When creating without specifying order, assign the next available order value.

## Error Responses

All errors return JSON:
```json
{
  "error": "Error message description"
}
```

Standard HTTP status codes:
- 400: Bad request (missing required fields, validation errors)
- 401: Unauthorized (missing X-API-Key)
- 403: Forbidden (insufficient permissions)
- 404: Not found
- 409: Conflict (e.g., duplicate global environment)
