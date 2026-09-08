# FitTrackee — Backend Implementation Spec

## Overview

FitTrackee is a **self-hosted outdoor activity tracker** (based on [FitTrackee](https://github.com/SamR1/FitTrackee), 1.1K★). Users log workouts (running, cycling, hiking, etc.), track personal records, manage equipment (shoes, bikes), and view statistics aggregated by sport or time period.

The application supports multiple users, each tracking their own activities independently.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (simplified):

- `X-User-Id`: UUID string identifying the current user

Rules:
- The `X-User-Id` header is required on every request except `GET /api/ping`.
- If the header is missing or empty, return `401 Unauthorized` with body `{"status": "error", "message": "unauthorized"}`.
- Trust the header value directly — if a user with that ID doesn't exist, **auto-create** the user with default profile values. The first auto-created user becomes admin (`is_admin: true`). Subsequent users are non-admin.
- **Data scoping**: All workouts, records, equipment, and statistics are scoped to the authenticated user. A user can only see/modify their own data.
- **Admin actions**: Only admins can update sport properties (toggle `is_active`). Non-admin users get `403 Forbidden`.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (15 paths, 24 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Ping — health check (1 path, 1 method)

- `GET /api/ping` — Returns `{"status": "ok"}`. No auth required.

### 2. User Profile — preferences (1 path, 2 methods)

- `GET /api/auth/profile` — Get current user's profile (includes computed stats: nb_workouts, nb_sports, total_distance, total_duration)
- `PATCH /api/auth/profile` — Update profile fields (username, first_name, last_name, birth_date, bio, location, language, timezone, display_ascent)

### 3. Sports — activity types (2 paths, 3 methods)

Predefined sport types. Admin can toggle `is_active`. Workouts can only reference active sports.

- `GET /api/sports` — List all sports
- `GET /api/sports/{sport_id}` — Get a single sport
- `PATCH /api/sports/{sport_id}` — Update sport (admin only; body: `is_active`)

Predefined sports (seeded on startup):
| id | label |
|----|-------|
| 1  | Cycling (Sport) |
| 2  | Cycling (Transport) |
| 3  | Hiking |
| 4  | Mountain Biking |
| 5  | Running |
| 6  | Walking |
| 7  | Trail |

All sports start as `is_active: true`.

### 4. Workouts — activity CRUD (2 paths, 5 methods)

Core entity. Each workout belongs to a user and references a sport.

- `GET /api/workouts` — Paginated list; filterable by sport_id, date range, title, equipment_id; orderable
- `POST /api/workouts` — Create a workout (201 on success)
- `GET /api/workouts/{workout_id}` — Get a single workout (includes records and equipment)
- `PATCH /api/workouts/{workout_id}` — Update a workout
- `DELETE /api/workouts/{workout_id}` — Delete a workout (204 on success)

### 5. Workout-Equipment linking (1 path, 2 methods)

- `POST /api/workouts/{workout_id}/equipments/{equipment_id}` — Link equipment to workout
- `DELETE /api/workouts/{workout_id}/equipments/{equipment_id}` — Unlink equipment from workout (204)

### 6. Records — personal bests (1 path, 1 method)

Auto-calculated from workouts. NOT directly modifiable.

- `GET /api/records` — Get current user's personal records

### 7. Statistics — aggregated data (2 paths, 2 methods)

Computed on read from workouts data.

- `GET /api/stats/{user_name}/by_sport` — Stats grouped by sport
- `GET /api/stats/{user_name}/by_time` — Stats grouped by time period (query param: `time` = week/month/year)

### 8. Equipment — gear management (2 paths, 5 methods)

Equipment (shoes, bikes, etc.) with accumulated totals from linked workouts.

- `GET /api/equipments` — List user's equipment (filterable by equipment_type_id)
- `POST /api/equipments` — Create equipment (201 on success)
- `GET /api/equipments/{equipment_id}` — Get single equipment
- `PATCH /api/equipments/{equipment_id}` — Update equipment
- `DELETE /api/equipments/{equipment_id}` — Delete equipment (204; fails with 400 if workouts linked)

### 9. Equipment Types — predefined (2 paths, 2 methods)

- `GET /api/equipment-types` — List all equipment types
- `GET /api/equipment-types/{type_id}` — Get single equipment type

Predefined equipment types (seeded on startup):
| id | label |
|----|-------|
| 1  | Shoe |
| 2  | Bike |
| 3  | Bike Trainer |
| 4  | Kayak/Boat |
| 5  | Skis |
| 6  | Snowshoes |

All equipment types start as `is_active: true`.

---

**Totals: 15 paths, 24 endpoints across 9 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 15 paths / 24 endpoints** matching `openapi.yaml` exactly
2. **Seeds predefined data on startup** (sports and equipment types — see tables above)
3. **Creates the database schema on startup**
4. **Auto-registers users** on first request with a given `X-User-Id`

Tech stack is your choice (language, framework, database, ORM — all up to you).

## Key Business Rules (not obvious from the API spec alone)

### 1. Auto-create users

When a request arrives with `X-User-Id: <uuid>`, if no user with that ID exists, create one with:
- `username`: `"user_"` + first 8 chars of UUID
- `language`: `"en"`
- `timezone`: `"UTC"`
- `display_ascent`: `true`
- `is_admin`: `true` only for the very first user created; `false` for all others

### 2. Sport validation

When creating or updating a workout, `sport_id` must reference:
- A sport that exists (otherwise `404`)
- A sport that is `is_active: true` (otherwise `400 Bad Request`)

### 3. Average speed computation

`ave_speed = distance / (duration / 3600.0)` (km/h). If duration is 0, ave_speed is 0. For no-GPX workouts, `max_speed` equals `ave_speed`.

### 4. Records auto-calculation

After any workout create/update/delete, recalculate the user's records for the affected sport(s). Record types:
- **FD** (Farthest Distance): workout with maximum `distance` for this sport
- **LD** (Longest Duration): workout with maximum `duration` (seconds) for this sport
- **MS** (Max Speed): workout with maximum `ave_speed` for this sport
- **HA** (Highest Ascent): workout with maximum `ascent` for this sport (only if ascent > 0)

Each record stores: `id`, `record_type`, `sport_id`, `workout_id`, `workout_date`, `value`, `user` (username).

Record `value` format:
- FD: float (km)
- LD: string `"H:MM:SS"`
- MS: float (km/h)
- HA: float (meters)

If no qualifying workouts remain for a sport+type, the record is deleted.

### 5. Equipment distance/duration accumulation

Equipment tracks:
- `total_distance`: sum of `distance` from all linked workouts (km)
- `total_duration`: sum of `duration` from all linked workouts (seconds)
- `workouts_count`: count of linked workouts

These auto-update when:
- Equipment is linked/unlinked to a workout
- A linked workout's distance or duration changes
- A linked workout is deleted

### 6. Equipment deletion constraint

Equipment CANNOT be deleted if any workouts are linked to it. Return `400 Bad Request` with message `"equipment has workouts linked, cannot delete"`.

### 7. Workout-equipment linking rules

- Equipment must belong to the same user as the workout
- Cannot link equipment that doesn't belong to the user → `403 Forbidden`
- Cannot link equipment to a workout that doesn't exist or belong to user → `404`
- Cannot link the same equipment twice → `400`
- Equipment must be `is_active: true` → `400`

### 8. Statistics computation

**By sport** (`GET /api/stats/{user_name}/by_sport`):
- Object keyed by sport_id (as string). Each value: `{"nb_workouts", "total_distance", "total_duration", "total_ascent", "total_descent"}`
- `total_duration` is integer seconds
- Only includes sports where the user has workouts

**By time** (`GET /api/stats/{user_name}/by_time`):
- Query param `time`: `week`, `month`, or `year` (default: `month`)
- Returns nested object: `{ "YYYY": { "N": { sport_id: {...stats...} } } }`
  - For `month`: N = 1-12
  - For `week`: N = ISO week number (1-53)
  - For `year`: N = "" (empty string — only year key matters)
- Each leaf: `{"nb_workouts", "total_distance", "total_duration", "total_ascent", "total_descent"}` per sport_id
- Can be filtered by `sport_id`, `from` (date), `to` (date)
- The user_name in the path must match the authenticated user's username. If not found, return 404.

### 9. Duration format

- **Input** (create/update): integer seconds (e.g., `3661`)
- **Output** (responses): formatted string `"H:MM:SS"` (e.g., `"1:01:01"`)
  - Hours are not zero-padded. Minutes and seconds are always 2 digits.
  - Examples: `"0:05:30"`, `"1:00:00"`, `"12:30:45"`

### 10. Pagination

Paginated endpoints (`GET /api/workouts`) return:
```json
{
  "status": "success",
  "data": { "workouts": [...] },
  "pagination": {
    "has_next": false,
    "has_prev": false,
    "page": 1,
    "pages": 1,
    "total": 5
  }
}
```

Defaults: `page=1`, `per_page=5`. Max `per_page`: 50.

### 11. Ordering

Workouts support:
- `order_by`: one of `workout_date`, `distance`, `duration`, `ave_speed` (default: `workout_date`)
- `order`: `asc` or `desc` (default: `desc`)
