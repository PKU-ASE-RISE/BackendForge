# Gotify — Backend Implementation Spec

## Overview

Gotify is a **self-hosted push notification server** (based on [Gotify](https://github.com/gotify/server), 14.9K stars). Users create applications that can push messages, and clients that can read messages. It supports multi-user with admin capabilities, message pagination, and priority-based filtering.

The application is deployed locally for self-hosted push notifications. A typical deployment handles thousands of messages across multiple applications.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified from the original Gotify token system):

- `X-Gotify-Key`: API key identifying the user

Rules:
- The `X-Gotify-Key` header is required on all endpoints **except** `/health` and `/version`.
- If the header is missing on a protected endpoint, return `401 Unauthorized`.
- Trust header values directly — the key IS the username. If a user with that name doesn't exist, **auto-create** the user (non-admin, with the key as their name). The first user auto-created becomes admin.
- **Data scoping**: All applications, clients, and messages are scoped to the authenticated user. A user can only see/modify their own data.
- **Admin endpoints**: User management (list/create/get/update/delete users at `/users` and `/users/{id}`) requires admin privileges. Non-admin users get `403 Forbidden`.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (20 paths, 27 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Applications — app token management (2 paths, 4 methods)

Each application gets a unique token for pushing messages. Applications belong to a user.

- `GET /applications` — List all applications for the current user
- `POST /applications` — Create an application (body: `name`, optional `description`, `defaultPriority`)
- `PUT /applications/{id}` — Update an application (body: `name`, optional `description`, `defaultPriority`)
- `DELETE /applications/{id}` — Delete an application (also deletes all its messages)

### 2. Messages — push notification CRUD (5 paths, 6 methods)

Messages are the core entity. They are created by applications and belong to a user.

- `GET /messages` — List all messages for the current user (supports `limit` and `since` pagination)
- `POST /messages` — Create a message (body: `message` required, optional `title`, `priority`, `extras`; requires `appid` in body OR the app's token as auth)
- `DELETE /messages` — Delete ALL messages for the current user
- `DELETE /messages/{id}` — Delete a single message
- `GET /applications/{id}/messages` — List messages for a specific application (supports `limit`, `since`)
- `DELETE /applications/{id}/messages` — Delete all messages for a specific application

### 3. Clients — device/reader management (2 paths, 4 methods)

Clients represent devices that receive notifications. Each client gets a unique token.

- `GET /clients` — List all clients for the current user
- `POST /clients` — Create a client (body: `name`)
- `PUT /clients/{id}` — Update a client (body: `name`)
- `DELETE /clients/{id}` — Delete a client

### 4. Users — multi-user admin (3 paths, 6 methods)

Admin-only user management plus current-user info.

- `GET /users` — List all users (admin only)
- `POST /users` — Create a user (admin only; body: `name`, `pass`, `admin`)
- `GET /users/{id}` — Get a user by ID (admin only)
- `PUT /users/{id}` — Update a user (admin only; body: `name`, `admin`, optional `pass`)
- `DELETE /users/{id}` — Delete a user (admin only; also deletes their apps, clients, messages)
- `GET /current/user` — Get the currently authenticated user

### 5. Health — system status (1 path, 1 method)

- `GET /health` — Returns health status (no auth required)

### 6. Version — build info (1 path, 1 method)

- `GET /version` — Returns version info (no auth required)

---

**Totals: 14 paths, 22 endpoints across 6 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 14 paths / 22 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create users**: When a request comes in with `X-Gotify-Key: somevalue`, if no user named `somevalue` exists, automatically create that user. The first auto-created user is admin. Subsequent auto-created users are non-admin.

2. **Application tokens**: When an application is created, generate a unique token (random string, at least 15 characters). This token is returned in the response and is immutable (cannot be changed via update).

3. **Client tokens**: When a client is created, generate a unique token (random string, at least 15 characters). This token is returned in the response and is immutable.

4. **Message creation with appid**: When creating a message via `POST /messages`, the `appid` field in the request body specifies which application sent the message. The application must belong to the current user. If appid is invalid or doesn't belong to the user, return `400 Bad Request`.

5. **Cascade delete — applications**: Deleting an application deletes all messages sent by that application.

6. **Cascade delete — users**: Deleting a user deletes all their applications, clients, and messages.

7. **Pagination (messages)**: Messages are returned newest-first (descending by ID). The `limit` parameter controls how many to return (1-200, default 100). The `since` parameter returns only messages with ID less than the given value (for cursor-based pagination). The response includes a `paging` object with `size`, `since`, `limit`, and `next` (URL for next page, or empty string if no more).

8. **Admin protection**: Only admin users can access `/users`, `/users/{id}` (GET/POST/PUT/DELETE). Non-admin users receive `403 Forbidden`. The `GET /current/user` endpoint is accessible to all authenticated users.

9. **Cannot delete self**: An admin cannot delete their own user account. Return `400 Bad Request`.

10. **Application ownership**: Users can only access/modify/delete their own applications. Attempting to access another user's application returns `404 Not Found`.

11. **Message ownership**: Users can only see/delete their own messages. Attempting to delete another user's message returns `404 Not Found`.

12. **Client ownership**: Users can only access/modify/delete their own clients. Attempting to access another user's client returns `404 Not Found`.

13. **Unique application names per user**: A user cannot have two applications with the same name. Return `400 Bad Request` on duplicate.

14. **Unique user names**: Two users cannot have the same name. Return `400 Bad Request` on duplicate.
