# Plane — Project Management Platform

## Overview

Plane is a project management platform similar to Jira/Linear. It supports workspaces, projects with custom workflow states, issues with priorities and assignees, sprint cycles, feature modules, saved views, wiki pages, comments with reactions, and activity logging.

## Authentication

All endpoints require an `X-API-Key` header. The API key identifies the acting user. If the header is missing or invalid, the API returns `401 Unauthorized`.

## Core Concepts

### Workspaces
Top-level organizational unit. All data is scoped to a workspace. Workspaces have a unique `slug` used in URL paths.

### Workspace Members
Users are added to workspaces with roles:
- **admin**: Full control — manage workspace settings, members, projects, states, labels
- **member**: Create/edit issues, comments, pages, cycles, modules, views
- **guest**: Read-only access to issues they are assigned to

### Projects
Projects live within a workspace. Each project has a unique `identifier` (uppercase prefix, e.g., "PROJ") used for issue numbering. Projects have their own member lists (subset of workspace members).

### States
Custom workflow states per project. Each state has a `group` field: `backlog`, `unstarted`, `started`, `completed`, or `cancelled`. States have a numeric `order` for sorting.

### Labels
Project-scoped labels with a `name` and hex `color` (e.g., "#ff0000").

### Issues
The core entity. Issues belong to a project and have:
- Auto-generated `identifier` as `{PROJECT_IDENTIFIER}-{sequence}` (e.g., "PROJ-1", "PROJ-2")
- `name` (title), `description`
- `stateId` (reference to a state)
- `priority` (one of: `urgent`, `high`, `medium`, `low`, `none`)
- `assignees` (list of member IDs)
- `labels` (list of label IDs)
- `dueDate` (ISO date string, optional)
- `estimate` (integer points, optional)
- `parentId` (for sub-issues, optional)

### Cycles (Sprints)
Time-boxed iterations with `startDate` and `endDate`. Issues can be added to/removed from cycles. End date must be after start date. Cycle detail includes analytics: total issues, completed issues (state group = "completed"), pending issues.

### Modules
Group issues by feature/epic. Modules have a `name`, `description`, optional `startDate`/`endDate`. Module detail includes progress: total issues and completed count.

### Views
Saved issue filters. A view has a `name` and `filters` object with optional keys: `stateId`, `priority`, `assignees`, `labels`, `dueDateStart`, `dueDateEnd`.

### Pages
Project wiki/notes. Pages have `title`, `content` (markdown), and optional `parentId` for nesting.

### Comments
Threaded comments on issues. Users can add emoji reactions to comments.

### Activity Log
Automatic tracking of issue changes. Each activity entry records: `field` changed, `oldValue`, `newValue`, `actorId`, `createdAt`.

## API Design

- All paths prefixed with `/api`
- Workspace scoped: `/api/workspaces/{workspaceSlug}/...`
- JSON request/response bodies
- Field names in camelCase
- UUIDs for all entity IDs
- Standard HTTP status codes: 200 (OK), 201 (Created), 204 (No Content for DELETE), 400 (Bad Request), 401 (Unauthorized), 403 (Forbidden), 404 (Not Found), 409 (Conflict)

## Endpoint Summary (~57 endpoints)

### Workspaces (5)
- POST /api/workspaces
- GET /api/workspaces
- GET /api/workspaces/{workspaceSlug}
- PATCH /api/workspaces/{workspaceSlug}
- DELETE /api/workspaces/{workspaceSlug}

### Workspace Members (4)
- POST /api/workspaces/{workspaceSlug}/members
- GET /api/workspaces/{workspaceSlug}/members
- PATCH /api/workspaces/{workspaceSlug}/members/{memberId}
- DELETE /api/workspaces/{workspaceSlug}/members/{memberId}

### Projects (5)
- POST /api/workspaces/{workspaceSlug}/projects
- GET /api/workspaces/{workspaceSlug}/projects
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}

### Project Members (3)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/members
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/members
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/members/{memberId}

### States (5)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/states
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/states
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/states/{stateId}
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}/states/{stateId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/states/{stateId}

### Labels (5)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/labels
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/labels
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/labels/{labelId}
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}/labels/{labelId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/labels/{labelId}

### Issues (5)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/issues
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/issues
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}

### Comments (4)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}/comments
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}/comments
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}/comments/{commentId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}/comments/{commentId}

### Reactions (2)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}/comments/{commentId}/reactions
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}/comments/{commentId}/reactions/{reactionId}

### Cycles (7)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/cycles
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/cycles
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/cycles/{cycleId}
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}/cycles/{cycleId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/cycles/{cycleId}
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/cycles/{cycleId}/issues
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/cycles/{cycleId}/issues/{issueId}

### Modules (7)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/modules
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/modules
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/modules/{moduleId}
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}/modules/{moduleId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/modules/{moduleId}
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/modules/{moduleId}/issues
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/modules/{moduleId}/issues/{issueId}

### Views (5)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/views
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/views
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/views/{viewId}
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}/views/{viewId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/views/{viewId}

### Pages (5)
- POST /api/workspaces/{workspaceSlug}/projects/{projectId}/pages
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/pages
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/pages/{pageId}
- PATCH /api/workspaces/{workspaceSlug}/projects/{projectId}/pages/{pageId}
- DELETE /api/workspaces/{workspaceSlug}/projects/{projectId}/pages/{pageId}

### Activity (1)
- GET /api/workspaces/{workspaceSlug}/projects/{projectId}/issues/{issueId}/activities

**Total: 58 endpoints**
