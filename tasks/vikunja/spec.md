# Vikunja — Backend Implementation Spec

## Overview

Vikunja is a **self-hosted task/project management application** (based on [Vikunja](https://github.com/go-vikunja/vikunja), 5K+ stars). It supports projects with nested hierarchy, tasks with rich metadata (priorities, due dates, labels, assignees, comments, relations), kanban boards with buckets, and multi-user collaboration with role-based access.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID string identifying the user

Rules:
- The `X-User-Id` header is required on **all** endpoints.
- If the header is missing or empty, return `401 Unauthorized`.
- Trust header values directly — the UUID IS the user identity. If a user with that ID doesn't exist in the database, **auto-create** the user with that ID and a default username of `user_<first 8 chars of UUID>`.
- **Data scoping**: Projects are private by default. Only the project owner and explicitly added members can access a project and its contents (tasks, buckets, etc.).

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (38 paths, ~48 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Projects — CRUD with hierarchy (3 paths, 5 methods)

Projects are the top-level organizational unit. They support nesting via `parent_project_id`.

- `GET /api/v1/projects` — List all projects accessible to the current user
- `POST /api/v1/projects` — Create a project (body: `title` required, optional `description`, `color`, `is_archived`, `position`, `parent_project_id`)
- `GET /api/v1/projects/{id}` — Get a project by ID
- `PUT /api/v1/projects/{id}` — Update a project
- `DELETE /api/v1/projects/{id}` — Delete a project (cascades to tasks, buckets, members)

### 2. Tasks — CRUD with rich metadata (3 paths, 5 methods)

Tasks belong to a project and carry extensive metadata.

- `GET /api/v1/projects/{id}/tasks` — List tasks in a project (supports `sort_by`, `order_by`, `filter_done`, `filter_priority`)
- `POST /api/v1/projects/{id}/tasks` — Create a task in a project
- `GET /api/v1/tasks/{id}` — Get a single task with all metadata
- `PUT /api/v1/tasks/{id}` — Update a task
- `DELETE /api/v1/tasks/{id}` — Delete a task

### 3. Labels — user-scoped CRUD (2 paths, 5 methods)

Labels are user-scoped — each user has their own set of labels.

- `GET /api/v1/labels` — List all labels for the current user
- `POST /api/v1/labels` — Create a label (body: `title` required, optional `color`, `description`)
- `GET /api/v1/labels/{id}` — Get a label by ID
- `PUT /api/v1/labels/{id}` — Update a label
- `DELETE /api/v1/labels/{id}` — Delete a label

### 4. Task Labels — attach/detach (1 path, 2 methods)

- `POST /api/v1/tasks/{id}/labels` — Attach a label to a task (body: `label_id`)
- `DELETE /api/v1/tasks/{id}/labels/{labelId}` — Detach a label from a task

### 5. Task Assignees — assign/unassign (1 path, 2 methods)

- `POST /api/v1/tasks/{id}/assignees` — Assign a user to a task (body: `user_id`)
- `DELETE /api/v1/tasks/{id}/assignees/{userId}` — Unassign a user from a task

### 6. Task Comments — CRUD (2 paths, 5 methods)

- `GET /api/v1/tasks/{id}/comments` — List comments on a task
- `POST /api/v1/tasks/{id}/comments` — Create a comment (body: `comment`)
- `GET /api/v1/tasks/{id}/comments/{commentId}` — Get a single comment
- `PUT /api/v1/tasks/{id}/comments/{commentId}` — Update a comment
- `DELETE /api/v1/tasks/{id}/comments/{commentId}` — Delete a comment

### 7. Task Relations — link tasks (1 path, 2 methods)

- `POST /api/v1/tasks/{id}/relations` — Create a relation (body: `other_task_id`, `relation_kind`)
- `DELETE /api/v1/tasks/{id}/relations/{relationType}/{otherTaskId}` — Delete a relation

### 8. Project Members — collaboration (2 paths, 4 methods)

- `GET /api/v1/projects/{id}/members` — List project members
- `POST /api/v1/projects/{id}/members` — Add a member (body: `user_id`, `role`)
- `PUT /api/v1/projects/{id}/members/{userId}` — Update member role
- `DELETE /api/v1/projects/{id}/members/{userId}` — Remove a member

### 9. Buckets — Kanban columns (2 paths, 5 methods)

- `GET /api/v1/projects/{id}/buckets` — List buckets in a project
- `POST /api/v1/projects/{id}/buckets` — Create a bucket (body: `title`, optional `position`, `limit`)
- `GET /api/v1/projects/{id}/buckets/{bucketId}` — Get a bucket
- `PUT /api/v1/projects/{id}/buckets/{bucketId}` — Update a bucket
- `DELETE /api/v1/projects/{id}/buckets/{bucketId}` — Delete a bucket

### 10. Task Buckets — move tasks between buckets (1 path, 1 method)

- `PUT /api/v1/tasks/{id}/bucket` — Move a task to a bucket (body: `bucket_id`)

### 11. Filters (Saved Filters) — saved search queries (2 paths, 5 methods)

- `GET /api/v1/filters` — List saved filters for the current user
- `POST /api/v1/filters` — Create a filter (body: `title`, `filter_query`)
- `GET /api/v1/filters/{id}` — Get a filter by ID
- `PUT /api/v1/filters/{id}` — Update a filter
- `DELETE /api/v1/filters/{id}` — Delete a filter

---

**Totals: 20 paths, ~48 endpoints across 11 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all paths/endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Auto-create users**: When a request comes with `X-User-Id: <uuid>`, if no user with that ID exists, auto-create them. Username defaults to `user_<first 8 chars of UUID>`.

2. **Project ownership**: The user who creates a project is automatically the owner. Only the owner can delete the project or manage members.

3. **Project access control**: A project is accessible only to its owner and explicitly added members. Accessing a project you don't have access to returns `403 Forbidden`. Accessing a non-existent project returns `404 Not Found`.

4. **Project hierarchy access**: If a user has access to a parent project, they automatically have access to all its child projects (recursive). However, having access to a child does NOT grant access to the parent.

5. **Archived projects**: If `is_archived` is true on a project, no tasks can be created or updated in that project. Attempting to do so returns `400 Bad Request` with an error message. Tasks can still be read. Archiving a parent does NOT automatically archive children.

6. **Task position**: Tasks have a `position` field (float). Used for ordering within a project. Default position is 0.

7. **Percent done**: Must be between 0.0 and 1.0 (inclusive). When a task's `done` field is set to `true`, `percent_done` is automatically set to 1.0. When `done` is set to `false`, `percent_done` is NOT automatically changed.

8. **Priority**: Integer from 0 (unset/default) to 5 (urgent). Values outside this range should be rejected with `400 Bad Request`.

9. **Task relations are bidirectional**: When you create relation "A blocks B", the system also creates the inverse "B blocked_by A". When you delete either side, both sides are deleted. Valid relation kinds: `related`, `duplicates`, `duplicated_by`, `blocks`, `blocked_by`, `subtask_of`, `parent_of`.

10. **Bucket limit**: If a bucket has a `limit` > 0, it cannot contain more tasks than that limit. Attempting to move a task to a full bucket returns `400 Bad Request`. A limit of 0 means unlimited.

11. **Task bucket assignment**: When a task is created, it is not assigned to any bucket (bucket_id is null). Tasks must be explicitly moved to buckets via `PUT /api/v1/tasks/{id}/bucket`.

12. **Cascade deletes**:
    - Deleting a project deletes all its tasks, buckets, and member associations
    - Deleting a task deletes all its comments, relations, label associations, and assignee associations
    - Deleting a label detaches it from all tasks

13. **Labels are user-scoped**: Each user has their own labels. A user cannot see or use another user's labels. Attaching a label you don't own to a task returns `400 Bad Request`.

14. **Task assignees**: Only users who are members (or owner) of the task's project can be assigned. Assigning a non-member returns `400 Bad Request`.

15. **Comment ownership**: Only the comment author can update or delete their comment. Others get `403 Forbidden`.

16. **Member roles**: `owner` (full control), `editor` (can create/edit tasks, buckets), `viewer` (read-only access to project and tasks). Viewers cannot create/edit/delete tasks, buckets, or comments. They get `403 Forbidden`.

17. **Filters are user-scoped**: Each user can only see/edit/delete their own saved filters.

18. **Due date format**: All dates are ISO 8601 strings (e.g., `2024-01-15T10:00:00Z`). Null means not set.

19. **Project listing**: `GET /api/v1/projects` returns all projects the user owns OR is a member of. Includes role info.

20. **Default bucket**: When the first bucket is created in a project, it becomes the default. Deleting a bucket that contains tasks returns `400 Bad Request` — tasks must be moved first.
