# Leantime — Goal-focused Project Management

A goal-focused project management tool inspired by [Leantime](https://github.com/Leantime/leantime). It supports OKR-style goal tracking, milestone planning, task management with sprints, timesheets, and client management.

## Tech Stack

Your choice.

## Authentication

Every request (except `GET /health`) must include two headers:

- `X-User-Id` — a UUID identifying the user. Trusted directly (no database lookup required).
- `X-Org-Id` — a UUID identifying the organization. Trusted directly.

If either header is missing or empty, return **401** with body `{"detail": "Unauthorized"}`.

All data is scoped to the organization (`X-Org-Id`). Users in one org cannot see or modify data from another org.

The `X-User-Id` is used for:
- Recording who created comments
- Recording who logged timesheets
- Assigning tasks (`assigned_to` field)

## Data Model

### Clients
- `id` (string, UUID, server-generated)
- `name` (string, required)
- `email` (string, optional)
- `phone` (string, optional)
- `company` (string, optional)
- `created_at` (string, ISO 8601 datetime, server-generated)

### Projects
- `id` (string, UUID, server-generated)
- `name` (string, required)
- `description` (string, optional, default "")
- `status` (string: `active`, `closed`, `archived`, default `active`)
- `start_date` (string, ISO 8601 date, optional)
- `end_date` (string, ISO 8601 date, optional)
- `client_id` (string, UUID, optional — references a Client)
- `progress` (number, computed — read-only, 0-100)
- `created_at` (string, ISO 8601 datetime, server-generated)

### Goals (OKRs)
- `id` (string, UUID, server-generated)
- `title` (string, required)
- `description` (string, optional, default "")
- `project_id` (string, UUID, required — references a Project)
- `metric_type` (string: `number`, `percent`, `boolean`, required)
- `target_value` (number, required)
- `current_value` (number, default 0)
- `parent_goal_id` (string, UUID, optional — references another Goal)
- `progress` (number, computed — read-only, 0-100)
- `created_at` (string, ISO 8601 datetime, server-generated)

### Milestones
- `id` (string, UUID, server-generated)
- `title` (string, required)
- `project_id` (string, UUID, required — references a Project)
- `due_date` (string, ISO 8601 date, optional)
- `status` (string: `open`, `in_progress`, `completed`, default `open`)
- `sort_order` (integer, default 0)
- `progress` (number, computed — read-only, percentage of completed tasks)
- `created_at` (string, ISO 8601 datetime, server-generated)

### Tasks (Tickets)
- `id` (string, UUID, server-generated)
- `title` (string, required)
- `description` (string, optional, default "")
- `project_id` (string, UUID, required — references a Project)
- `milestone_id` (string, UUID, optional — references a Milestone)
- `assigned_to` (string, UUID, optional — user ID)
- `status` (string: `new`, `in_progress`, `done`, `blocked`, default `new`)
- `priority` (string: `low`, `medium`, `high`, `urgent`, default `medium`)
- `due_date` (string, ISO 8601 date, optional)
- `estimated_hours` (number, optional, default 0)
- `spent_hours` (number, computed — sum of timesheet hours for this task, read-only)
- `tags` (array of strings, default [])
- `created_at` (string, ISO 8601 datetime, server-generated)

### Timesheets
- `id` (string, UUID, server-generated)
- `task_id` (string, UUID, required — references a Task)
- `user_id` (string, UUID, server-set from X-User-Id header)
- `hours` (number, required, must be > 0)
- `date` (string, ISO 8601 date, required)
- `description` (string, optional, default "")
- `created_at` (string, ISO 8601 datetime, server-generated)

### Comments
- `id` (string, UUID, server-generated)
- `task_id` (string, UUID, set from URL path)
- `user_id` (string, UUID, server-set from X-User-Id header)
- `content` (string, required)
- `created_at` (string, ISO 8601 datetime, server-generated)

### Sprints
- `id` (string, UUID, server-generated)
- `name` (string, required)
- `project_id` (string, UUID, required — references a Project)
- `start_date` (string, ISO 8601 date, required)
- `end_date` (string, ISO 8601 date, required)
- `tasks` (array of task IDs, read-only on GET)
- `velocity` (number, computed — sum of estimated_hours of done tasks in sprint, read-only)
- `created_at` (string, ISO 8601 datetime, server-generated)

## Endpoints

### Health
- `GET /health` — No auth required. Returns `{"status": "ok"}`.

### Clients (5 endpoints)
- `GET /clients` — List all clients in org
- `POST /clients` — Create client (201)
- `GET /clients/{client_id}` — Get client by ID
- `PUT /clients/{client_id}` — Update client
- `DELETE /clients/{client_id}` — Delete client (204)

### Projects (5 endpoints)
- `GET /projects` — List all projects in org. Supports `?status=active` filter.
- `POST /projects` — Create project (201). If `client_id` provided, must reference existing client.
- `GET /projects/{project_id}` — Get project by ID. Includes computed `progress` field.
- `PUT /projects/{project_id}` — Update project. Cannot set status to `closed` if there are non-completed milestones.
- `DELETE /projects/{project_id}` — Delete project and all associated milestones, tasks, goals, sprints (204).

### Goals (5 endpoints)
- `GET /goals` — List all goals in org. Supports `?project_id=` filter.
- `POST /goals` — Create goal (201). `project_id` must reference existing project. If `parent_goal_id` provided, must reference existing goal in same project.
- `GET /goals/{goal_id}` — Get goal by ID. Includes computed `progress`.
- `PUT /goals/{goal_id}` — Update goal.
- `DELETE /goals/{goal_id}` — Delete goal. If goal has children, children become orphans (parent_goal_id set to null).

### Milestones (5 endpoints)
- `GET /milestones` — List all milestones in org. Supports `?project_id=` filter. Ordered by `sort_order`.
- `POST /milestones` — Create milestone (201). `project_id` must reference existing project.
- `GET /milestones/{milestone_id}` — Get milestone by ID. Includes computed `progress`.
- `PUT /milestones/{milestone_id}` — Update milestone.
- `DELETE /milestones/{milestone_id}` — Delete milestone. Returns 409 if milestone has tasks assigned to it.

### Tasks (5 endpoints)
- `GET /tasks` — List all tasks in org. Supports filters: `?project_id=`, `?milestone_id=`, `?assigned_to=`, `?status=`, `?priority=`, `?tags=` (comma-separated, match any).
- `POST /tasks` — Create task (201). `project_id` must reference existing project. If `milestone_id` provided, must reference existing milestone in same project.
- `GET /tasks/{task_id}` — Get task by ID. Includes computed `spent_hours`.
- `PUT /tasks/{task_id}` — Update task. Status transitions are validated (see Business Rules).
- `DELETE /tasks/{task_id}` — Delete task and associated timesheets/comments (204).

### Comments (3 endpoints)
- `GET /tasks/{task_id}/comments` — List comments for a task, ordered by created_at ascending.
- `POST /tasks/{task_id}/comments` — Add comment to task (201). `user_id` set from header.
- `DELETE /comments/{comment_id}` — Delete a comment (204). Only the comment author (matching X-User-Id) can delete.

### Timesheets (5 endpoints)
- `GET /timesheets` — List timesheets in org. Supports filters: `?task_id=`, `?user_id=`, `?date_from=`, `?date_to=`.
- `POST /timesheets` — Create timesheet entry (201). `task_id` must reference existing task. `user_id` set from header.
- `GET /timesheets/{timesheet_id}` — Get timesheet entry by ID.
- `PUT /timesheets/{timesheet_id}` — Update timesheet entry. Only the author can update.
- `DELETE /timesheets/{timesheet_id}` — Delete timesheet entry (204). Only the author can delete.

### Timesheets Summary (1 endpoint)
- `GET /timesheets/summary` — Get aggregated hours. Supports `?project_id=`, `?user_id=`, `?task_id=`. Returns `{"total_hours": <number>, "entries_count": <number>}`.

### Sprints (8 endpoints)
- `GET /sprints` — List sprints in org. Supports `?project_id=` filter.
- `POST /sprints` — Create sprint (201). `project_id` must reference existing project.
- `GET /sprints/{sprint_id}` — Get sprint by ID. Includes `tasks` (list of task IDs) and computed `velocity`.
- `PUT /sprints/{sprint_id}` — Update sprint.
- `DELETE /sprints/{sprint_id}` — Delete sprint (204). Tasks are NOT deleted, just unlinked from the sprint.
- `POST /sprints/{sprint_id}/tasks` — Add a task to sprint. Body: `{"task_id": "..."}`. Task must belong to same project. Returns 200 with sprint.
- `DELETE /sprints/{sprint_id}/tasks/{task_id}` — Remove task from sprint (204).
- `GET /sprints/{sprint_id}/velocity` — Get sprint velocity: `{"velocity": <number>, "completed_tasks": <number>, "total_tasks": <number>}`.

**Total: 42 endpoints**

## Business Rules

### Goal Progress Calculation
- For `metric_type: "number"` or `"percent"`: `progress = (current_value / target_value) * 100`, clamped to 0-100.
- For `metric_type: "boolean"`: `progress = 100` if `current_value >= 1`, else `0`.
- If `target_value` is 0, progress is 0.
- **Goal hierarchy**: If a goal has child goals, its progress is the **average** of its children's progress values (ignoring its own current_value/target_value).

### Milestone Progress
- `progress` = (number of tasks with status `done` in this milestone) / (total tasks in this milestone) * 100.
- If milestone has no tasks, progress is 0.

### Project Progress
- `progress` = average of all milestone progress values in the project.
- If project has no milestones, progress is 0.

### Sprint Velocity
- `velocity` = sum of `estimated_hours` of all tasks in the sprint that have status `done`.

### Task Status Transitions
Valid transitions:
- `new` → `in_progress`
- `in_progress` → `done`
- `in_progress` → `blocked`
- `new` → `blocked`
- `blocked` → `new`
- `blocked` → `in_progress`
- `done` → `in_progress` (reopen)

Invalid transitions return **422** with `{"detail": "Invalid status transition from '<current>' to '<target>'"}`.

Setting the same status as current is always allowed (no-op).

### Project Closure Rule
- Cannot set project status to `closed` if any milestone in the project has status != `completed`.
- Returns **409** with `{"detail": "Cannot close project with open milestones"}`.

### Milestone Deletion Rule
- Cannot delete a milestone that has tasks assigned to it.
- Returns **409** with `{"detail": "Cannot delete milestone with assigned tasks"}`.

### Timesheet/Comment Ownership
- Timesheets and comments record the `user_id` from the `X-User-Id` header.
- Only the author can update/delete their own timesheets.
- Only the author can delete their own comments.
- Attempting to modify another user's timesheet/comment returns **403** with `{"detail": "Forbidden"}`.

### Referential Integrity
- Creating a task with a non-existent `project_id` → **404** with `{"detail": "Project not found"}`.
- Creating a task with a non-existent `milestone_id` → **404** with `{"detail": "Milestone not found"}`.
- Creating a goal with a non-existent `project_id` → **404** with `{"detail": "Project not found"}`.
- Creating a timesheet with a non-existent `task_id` → **404** with `{"detail": "Task not found"}`.
- Creating a project with a non-existent `client_id` → **404** with `{"detail": "Client not found"}`.
- Adding a task to a sprint where the task belongs to a different project → **400** with `{"detail": "Task does not belong to sprint project"}`.
- Resource not found → **404** with `{"detail": "<Resource> not found"}`.

### Data Isolation
- All queries filter by `org_id` from the `X-Org-Id` header.
- A request from org A cannot see, modify, or delete data created by org B.
- Attempting to access another org's resource returns **404** (as if it doesn't exist).
