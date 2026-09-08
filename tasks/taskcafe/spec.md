# TaskCafe — Backend Implementation Spec

## Overview

TaskCafe is a **Kanban-style project management tool** (inspired by [TaskCafe](https://github.com/JordanKnott/taskcafe), 4.1K stars). Users create projects with task groups (columns), add tasks (cards) with checklists, labels, comments, and assignments. It supports team collaboration with role-based access control.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID identifying the user

Rules:
- The `X-User-Id` header is required on all endpoints.
- If the header is missing, return `401 Unauthorized` with body `{"error": "missing X-User-Id header"}`.
- If the header is present but not a valid UUID format, return `401 Unauthorized` with body `{"error": "invalid X-User-Id header"}`.
- Trust the header value directly — no password or token verification. The UUID IS the user identity.
- **Data scoping**: All data is scoped by project membership. A user can only see/modify resources (tasks, task groups, labels, etc.) within projects they are a member of.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (38 endpoints). Your implementation must match this contract exactly — response structure, field names (camelCase), status codes.

---

### 1. Projects — team workspaces (5 endpoints)

- `GET /projects` — List all projects the current user is a member of
- `POST /projects` — Create a project (creator automatically becomes owner)
- `GET /projects/{projectId}` — Get project details (includes member list)
- `PUT /projects/{projectId}` — Update project name (admin/owner only)
- `DELETE /projects/{projectId}` — Delete project and all its data (owner only)

### 2. Project Members — team management (3 endpoints)

- `GET /projects/{projectId}/members` — List project members with roles
- `POST /projects/{projectId}/members` — Add a member (admin/owner only)
- `DELETE /projects/{projectId}/members/{userId}` — Remove a member (admin/owner only; cannot remove the owner)

### 3. Task Groups — Kanban columns (4 endpoints)

- `GET /projects/{projectId}/task-groups` — List task groups (ordered by position)
- `POST /projects/{projectId}/task-groups` — Create a task group
- `PUT /task-groups/{taskGroupId}` — Update task group (name, position)
- `DELETE /task-groups/{taskGroupId}` — Delete task group (and all tasks in it)

### 4. Tasks — Kanban cards (5 endpoints)

- `GET /projects/{projectId}/tasks` — List tasks (supports filtering by complete, dueDate, taskGroupId)
- `POST /tasks` — Create a task (provide taskGroupId; auto-assigned position at end)
- `GET /tasks/{taskId}` — Get task with all details (assigned members, labels, checklists)
- `PUT /tasks/{taskId}` — Update task fields (title, description, position, taskGroupId, dueDate, complete)
- `DELETE /tasks/{taskId}` — Delete task and all related data

### 5. Task Assignments — assign members to tasks (2 endpoints)

- `POST /tasks/{taskId}/assignments` — Assign a project member to a task
- `DELETE /tasks/{taskId}/assignments/{userId}` — Unassign a member from a task

### 6. Labels — per-project color tags (4 endpoints)

- `GET /projects/{projectId}/labels` — List project labels
- `POST /projects/{projectId}/labels` — Create a label
- `PUT /labels/{labelId}` — Update label (name, color)
- `DELETE /labels/{labelId}` — Delete label (removes from all tasks)

### 7. Task Labels — attach labels to tasks (2 endpoints)

- `POST /tasks/{taskId}/labels` — Add a label to a task
- `DELETE /tasks/{taskId}/labels/{labelId}` — Remove a label from a task

### 8. Checklists — task sub-items grouped (3 endpoints)

- `POST /tasks/{taskId}/checklists` — Create a checklist
- `PUT /checklists/{checklistId}` — Update checklist (title, position)
- `DELETE /checklists/{checklistId}` — Delete checklist and all its items

### 9. Checklist Items — individual checklist entries (3 endpoints)

- `POST /checklists/{checklistId}/items` — Create a checklist item
- `PUT /checklist-items/{itemId}` — Update item (name, complete, position)
- `DELETE /checklist-items/{itemId}` — Delete item

### 10. Comments — discussion on tasks (4 endpoints)

- `GET /tasks/{taskId}/comments` — List comments on a task
- `POST /tasks/{taskId}/comments` — Add a comment
- `PUT /comments/{commentId}` — Edit a comment (author only)
- `DELETE /comments/{commentId}` — Delete a comment (author only)

### 11. Activity Log — audit trail (1 endpoint)

- `GET /projects/{projectId}/activity` — List activity entries (newest first, supports pagination)

---

**Totals: 36 endpoints across 11 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 36 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

1. **Project membership required**: A user can only access resources (tasks, task groups, labels, comments, etc.) within projects they are a member of. Attempting to access a project you're not a member of returns `403 Forbidden` with body `{"error": "not a project member"}`.

2. **Role hierarchy**: Roles are `owner` > `admin` > `member`.
   - **owner**: Full control. Can delete project, manage members (add/remove anyone), update project.
   - **admin**: Can manage members (add/remove members, but not the owner), update project, full CRUD on all project resources.
   - **member**: Can CRUD tasks, task groups, labels, checklists, comments, assignments within the project. Cannot manage project settings or members.

3. **Project creation**: When a project is created, the creator is automatically added as `owner`. The response includes the member list with the owner.

4. **Float-based positioning**: Task groups and tasks use float-based position values. When creating a new item without specifying position, assign a position greater than all existing items (e.g., max_position + 65536, or 65536 if none exist). When updating position, accept any float value — this allows inserting between items without rewriting all positions.

5. **Task movement between groups**: Updating a task's `taskGroupId` moves it to another group. The task's position should also be updated (client provides new position).

6. **Task completion does NOT cascade**: Marking a task as complete does NOT auto-complete its checklist items. They remain in their current state.

7. **Checklist progress**: When retrieving a task (GET /tasks/{taskId}), each checklist in the response includes computed fields `completedItems` (count of items where complete=true) and `totalItems` (total count of items).

8. **Labels are per-project**: Labels belong to a specific project. A label can only be attached to tasks within the same project. Attempting to add a label from a different project returns `400 Bad Request`.

9. **Activity log auto-generation**: The following actions automatically create an activity entry:
   - Task created (`TASK_CREATED`)
   - Task completed/uncompleted (`TASK_COMPLETED` / `TASK_UNCOMPLETED`)
   - Task moved to different group (`TASK_MOVED`)
   - Task assigned (`TASK_ASSIGNED`)
   - Task unassigned (`TASK_UNASSIGNED`)
   - Comment added (`COMMENT_ADDED`)

   Each activity entry records: projectId, taskId (if applicable), userId (who performed the action), actionType, detail (human-readable string), createdAt.

10. **Due date filtering**: `GET /projects/{projectId}/tasks` supports an `overdue=true` query parameter that filters to tasks where `dueDate < today AND complete = false`. The `today` comparison uses the server's current date (UTC).

11. **Cannot remove owner**: The owner cannot be removed from the project via the remove member endpoint. Return `400 Bad Request` with `{"error": "cannot remove project owner"}`.

12. **Cannot delete non-empty task group without cascade**: Deleting a task group that contains tasks will delete those tasks and all their related data (assignments, labels, checklists, comments, activity).

13. **Comment author restriction**: Only the comment author can edit or delete their comment. Other project members get `403 Forbidden` with `{"error": "not comment author"}`.

14. **Assignment validation**: You can only assign users who are members of the project. Attempting to assign a non-member returns `400 Bad Request` with `{"error": "user is not a project member"}`.

15. **Duplicate prevention**:
    - Cannot add the same user to a project twice (return `409 Conflict`)
    - Cannot assign the same user to a task twice (return `409 Conflict`)
    - Cannot add the same label to a task twice (return `409 Conflict`)
