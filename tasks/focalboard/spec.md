# Focalboard — Backend Implementation Spec

## Overview

Focalboard is a **Kanban board / project management tool** (inspired by [Mattermost Focalboard](https://github.com/mattermost/focalboard), 22K+ stars). Users create boards with custom properties, organize cards into views, and collaborate via board membership. Think Trello/Notion boards with custom fields.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID identifying the user

Rules:
- The `X-User-Id` header is required on **all** endpoints.
- If the header is missing or empty, return `401 Unauthorized`.
- Trust the header value directly — no database lookup to verify the user. The UUID IS the user identity.
- **Data scoping**: Boards are private by default. Users can only see boards they created or are a member of.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (34 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Boards — CRUD (4 endpoints)

Boards are the top-level container. Each board has a title, description, type, and defines custom properties.

- `POST /boards` — Create a board (201)
- `GET /boards` — List boards accessible to the current user (owned + member of)
- `GET /boards/{boardId}` — Get a single board
- `PUT /boards/{boardId}` — Update a board
- `DELETE /boards/{boardId}` — Delete a board (cascades: deletes all cards, views, comments, blocks, members)

### 2. Board Properties — custom field definitions (3 endpoints)

Properties define the schema for card fields on a board. Each property has a name, type, and optional options (for select/multiSelect).

- `POST /boards/{boardId}/properties` — Add a property to a board (201)
- `PUT /boards/{boardId}/properties/{propertyId}` — Update a property
- `DELETE /boards/{boardId}/properties/{propertyId}` — Delete a property (also removes this property's values from all cards)

### 3. Cards — CRUD (5 endpoints)

Cards are the items on a board. Each card has a title, properties (key-value matching the board's property definitions), content (markdown), and an order field.

- `POST /boards/{boardId}/cards` — Create a card (201)
- `GET /boards/{boardId}/cards` — List cards on a board (supports `sort_by`, `filter_property`, `filter_value`)
- `GET /boards/{boardId}/cards/{cardId}` — Get a single card
- `PUT /boards/{boardId}/cards/{cardId}` — Update a card
- `DELETE /boards/{boardId}/cards/{cardId}` — Delete a card (cascades: deletes comments and content blocks)

### 4. Views — CRUD (4 endpoints)

Views define how cards are displayed — type, filters, sorts, grouping, visible properties.

- `POST /boards/{boardId}/views` — Create a view (201)
- `GET /boards/{boardId}/views` — List views on a board
- `GET /boards/{boardId}/views/{viewId}` — Get a single view
- `PUT /boards/{boardId}/views/{viewId}` — Update a view
- `DELETE /boards/{boardId}/views/{viewId}` — Delete a view

### 5. Comments — CRUD on cards (4 endpoints)

Comments are threaded discussions on cards.

- `POST /boards/{boardId}/cards/{cardId}/comments` — Add a comment (201)
- `GET /boards/{boardId}/cards/{cardId}/comments` — List comments on a card
- `PUT /boards/{boardId}/cards/{cardId}/comments/{commentId}` — Update a comment
- `DELETE /boards/{boardId}/cards/{cardId}/comments/{commentId}` — Delete a comment

### 6. Board Members — sharing (4 endpoints)

Control access to boards by adding/removing members with specific roles.

- `POST /boards/{boardId}/members` — Add a member to a board (201)
- `GET /boards/{boardId}/members` — List board members
- `PUT /boards/{boardId}/members/{userId}` — Update a member's role
- `DELETE /boards/{boardId}/members/{userId}` — Remove a member

### 7. Content Blocks — structured card content (4 endpoints)

Blocks are structured content elements within a card (beyond the card's markdown content field).

- `POST /boards/{boardId}/cards/{cardId}/blocks` — Add a content block (201)
- `GET /boards/{boardId}/cards/{cardId}/blocks` — List content blocks for a card
- `PUT /boards/{boardId}/cards/{cardId}/blocks/{blockId}` — Update a content block
- `DELETE /boards/{boardId}/cards/{cardId}/blocks/{blockId}` — Delete a content block

### 8. Templates — board templates (4 endpoints)

Templates are special boards marked as templates. Users can create new boards from templates.

- `POST /templates` — Create a template (a board marked as template) (201)
- `GET /templates` — List all templates created by the current user
- `GET /templates/{templateId}` — Get a template
- `POST /templates/{templateId}/create-board` — Create a new board from a template (201, deep-copies properties and views)

---

**Totals: 34 endpoints across 8 groups.**

## Key Business Rules (not obvious from the API spec alone)

### Board Access Control

1. **Board creator is automatically admin**: When a board is created, the creator is implicitly an admin member (no explicit member record needed — the `createdBy` field grants admin access).

2. **Member roles and permissions**:
   - `admin` — Full access: CRUD on board, cards, views, comments, blocks, members
   - `editor` — Can create/update/delete cards, comments, blocks, views. Cannot modify board settings or manage members.
   - `commenter` — Can create/update/delete their own comments only. Can read cards, views, blocks. Cannot create/modify cards, views, or blocks.
   - `viewer` — Read-only access to board, cards, views, comments, blocks. Cannot create or modify anything.

3. **Board visibility**: A user can only access a board if they are the creator OR a member. All other users get `404 Not Found` (not 403, to avoid leaking board existence).

4. **Only admins can manage members**: Adding, updating, or removing members requires admin role. Non-admins get `403 Forbidden`.

5. **Only admins can update/delete the board itself**: Modifying board-level settings (title, description, type) or deleting the board requires admin. Non-admins get `403 Forbidden`.

### Card Properties Validation

6. **Card property values must reference valid board properties**: When creating/updating a card, the `properties` object's keys must be IDs of properties defined on the board. Unknown property IDs are silently ignored (not stored).

7. **Select/multiSelect validation**: If a property is of type `select`, the card's value for that property must be one of the defined option IDs. If type is `multiSelect`, the value must be an array where each element is a valid option ID. Invalid option values return `400 Bad Request`.

8. **Property deletion cascades to cards**: When a board property is deleted, all cards on that board have that property key removed from their `properties` object.

### Views

9. **View filter structure**: A view's `filter` field is an object with `operator` ("and"/"or") and `conditions` array. Each condition has `propertyId`, `operator` (e.g., "equals", "notEquals", "contains", "notContains", "isEmpty", "isNotEmpty"), and `value`.

10. **View sort structure**: A view's `sort` field is an array of objects, each with `propertyId` and `direction` ("asc"/"desc").

11. **View groupBy**: The `groupBy` field is a property ID that must reference a `select` type property. This creates swimlanes by the property's option values.

### Templates

12. **Template deep-copy**: Creating a board from a template copies:
    - Board title (can be overridden), description, type
    - All board properties (with new IDs)
    - All views (with new IDs, and property references updated to new property IDs)
    - Does NOT copy cards, comments, blocks, or members

13. **Templates are owned by creators**: Only the template creator can see/modify/delete their templates.

### Cards

14. **Card ordering**: Cards have an `order` float field (default 0). Cards should be returned sorted by `order` ascending, then by `createdAt` ascending as tiebreaker.

15. **Card sort/filter via query params**: `GET /boards/{boardId}/cards` supports:
    - `sort_by`: property ID to sort by (sorts by card's property value for that ID)
    - `filter_property` + `filter_value`: filter cards where the specified property equals the given value

### Comments

16. **Comment ownership**: Users can only update/delete their own comments. Attempting to modify another user's comment returns `403 Forbidden`.

### Content Blocks

17. **Block ordering**: Blocks have an `order` float field. Blocks are returned sorted by `order` ascending.

18. **Block types**: Valid types are `text`, `image`, `divider`, `checkbox`. Invalid types return `400 Bad Request`.

### General

19. **UUID format**: All IDs (boards, cards, views, properties, comments, blocks, members) are UUIDs generated server-side.

20. **Timestamps**: `createdAt` and `updatedAt` fields are ISO 8601 format, generated server-side.

21. **404 for wrong board context**: If a card/view/comment/block doesn't belong to the specified board in the URL path, return `404 Not Found`.

22. **Delete returns 204 No Content**: All DELETE operations return 204 with no body on success.
