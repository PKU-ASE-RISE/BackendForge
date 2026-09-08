# Formbricks — Backend Implementation Spec

## Overview

Formbricks is an **open-source survey platform** (based on [Formbricks](https://github.com/formbricks/formbricks), 12K★). Users create surveys with various question types, collect responses, track respondents (people/contacts), define audience segments, organize surveys with tags, and view response analytics including NPS scores and completion rates.

The application supports multiple environments (production/development) with data isolation between them.

## Tech Stack

- **Language**: Your choice
- **Framework**: Your choice
- **Database**: Your choice (PostgreSQL, SQLite, in-memory, etc.)
- **ORM**: Your choice

## Authentication

Header-based auth (no JWT/OAuth):
- `X-User-Id`: UUID of the current user
- `X-Environment-Id`: UUID of the environment

Rules:
- Both headers are required on every request. If either is missing, return `401 Unauthorized`.
- Trust header values directly — no database lookup to verify the IDs is required.
- **Data scoping**: All data (surveys, questions, responses, people, segments, tags, webhooks) is scoped to `environment_id`.
- **Isolation**: A request with environment A's ID must never see or modify data belonging to environment B.

## API Contract

The full OpenAPI 3.0 spec is in **`openapi.yaml`** (22 paths, 44 endpoints). Your implementation must match this contract exactly — response structure, field names, status codes.

---

### 1. Surveys — CRUD + lifecycle (3 paths, 7 methods)

Surveys are the core entity. They support a state machine lifecycle and contain configuration for welcome/thank-you cards.

- `GET /api/surveys` — List all surveys in the environment. Supports `?status=` filter (draft/active/paused/completed).
- `POST /api/surveys` — Create a new survey (starts in `draft` status by default).
- `GET /api/surveys/{surveyId}` — Get survey detail including all questions (embedded).
- `PUT /api/surveys/{surveyId}` — Full update of survey fields.
- `PATCH /api/surveys/{surveyId}/status` — Change survey status (lifecycle transitions).
- `DELETE /api/surveys/{surveyId}` — Delete a survey and all related data.
- `GET /api/surveys/{surveyId}/analytics` — Get response analytics for the survey.

### 2. Questions — CRUD within a survey (2 paths, 5 methods)

Questions belong to a survey and have a `position` field for ordering.

- `GET /api/surveys/{surveyId}/questions` — List all questions for a survey (ordered by position).
- `POST /api/surveys/{surveyId}/questions` — Add a question to a survey.
- `GET /api/surveys/{surveyId}/questions/{questionId}` — Get a single question.
- `PUT /api/surveys/{surveyId}/questions/{questionId}` — Update a question.
- `DELETE /api/surveys/{surveyId}/questions/{questionId}` — Delete a question (reorders remaining).

### 3. Responses — collect + list (2 paths, 4 methods)

Responses contain answers keyed by question ID.

- `GET /api/surveys/{surveyId}/responses` — List all responses for a survey. Supports `?finished=true/false` filter.
- `POST /api/surveys/{surveyId}/responses` — Submit a response to a survey.
- `GET /api/surveys/{surveyId}/responses/{responseId}` — Get a single response.
- `DELETE /api/surveys/{surveyId}/responses/{responseId}` — Delete a response.

### 4. People/Contacts — respondent tracking (2 paths, 5 methods)

Optional respondent identity tracking.

- `GET /api/people` — List all people in the environment.
- `POST /api/people` — Create a person.
- `GET /api/people/{personId}` — Get a single person.
- `PUT /api/people/{personId}` — Update a person.
- `DELETE /api/people/{personId}` — Delete a person.

### 5. Environments — environment info (1 path, 1 method)

- `GET /api/environments/current` — Get current environment info (based on X-Environment-Id header).

### 6. Survey Triggers — activation rules (2 paths, 5 methods)

Define when a survey should be shown.

- `GET /api/surveys/{surveyId}/triggers` — List triggers for a survey.
- `POST /api/surveys/{surveyId}/triggers` — Create a trigger.
- `GET /api/surveys/{surveyId}/triggers/{triggerId}` — Get a single trigger.
- `PUT /api/surveys/{surveyId}/triggers/{triggerId}` — Update a trigger.
- `DELETE /api/surveys/{surveyId}/triggers/{triggerId}` — Delete a trigger.

### 7. Tags — survey organization (2 paths, 5 methods)

Tags help organize surveys into categories.

- `GET /api/tags` — List all tags in the environment.
- `POST /api/tags` — Create a tag (body: `name`).
- `GET /api/tags/{tagId}` — Get a single tag.
- `PUT /api/tags/{tagId}` — Update a tag name.
- `DELETE /api/tags/{tagId}` — Delete a tag (removes all associations).

### 8. Survey Tags — link tags to surveys (1 path, 2 methods)

- `POST /api/surveys/{surveyId}/tags` — Add a tag to a survey (body: `tagId`).
- `DELETE /api/surveys/{surveyId}/tags/{tagId}` — Remove a tag from a survey.

### 9. Segments — audience targeting (3 paths, 6 methods)

Segments define groups of people based on attribute filters.

- `GET /api/segments` — List all segments in the environment.
- `POST /api/segments` — Create a segment (body: `name`, `filters`).
- `GET /api/segments/{segmentId}` — Get a single segment.
- `PUT /api/segments/{segmentId}` — Update a segment.
- `DELETE /api/segments/{segmentId}` — Delete a segment.
- `GET /api/segments/{segmentId}/people` — List people matching this segment's filters.

### 10. Webhooks — event notifications (2 paths, 4 methods)

Webhooks notify external systems about survey events.

- `GET /api/webhooks` — List all webhooks in the environment.
- `POST /api/webhooks` — Create a webhook (body: `url`, `triggers`).
- `GET /api/webhooks/{webhookId}` — Get a single webhook.
- `DELETE /api/webhooks/{webhookId}` — Delete a webhook.

---

**Totals: 22 paths, 44 endpoints across 10 endpoint groups.**

## What You Need to Deliver

A backend application that:

1. **Implements all 22 paths / 44 endpoints** matching `openapi.yaml` exactly
2. **Creates the database schema on startup** (you design all tables, indexes, relationships)
3. **Starts empty** — no seed data on startup

Tech stack is your choice.

## Key Business Rules (not obvious from the API spec alone)

1. **Survey lifecycle state machine**: Status transitions follow these rules:
   - `draft` → `active` (activate the survey)
   - `active` → `paused` (pause the survey)
   - `active` → `completed` (complete the survey)
   - `paused` → `active` (resume the survey)
   - `paused` → `completed` (complete while paused)
   - `completed` → (terminal state, cannot be reactivated or changed)
   - Any other transition returns `400 Bad Request`.

2. **Only active surveys accept responses**: Submitting a response to a non-active survey returns `400 Bad Request` with an error message.

3. **Required field validation**: When submitting a response, if a question has `required=true`, the response `data` object MUST include a non-empty answer for that question's ID. Missing or empty required answers return `422 Unprocessable Entity`.

4. **Question position ordering**: Questions have a `position` field (integer, 1-based). Positions must be unique within a survey. When a question is deleted, remaining questions' positions are compacted (no gaps). When creating a question without specifying position, it gets the next available position (max + 1).

5. **Survey auto-close**: When a survey has `closesAt` set and that timestamp is in the past, the survey behaves as if completed — new responses are rejected with `400`. The `status` field in GET responses should reflect `completed` if `closesAt` is in the past (regardless of stored status, unless already completed).

6. **NPS calculation** (in analytics):
   - Promoters: respondents who answered 9 or 10
   - Passives: respondents who answered 7 or 8
   - Detractors: respondents who answered 0–6
   - NPS = ((promoters_count / total_nps_responses) - (detractors_count / total_nps_responses)) * 100
   - Only applies to questions with type `nps`. Rounded to nearest integer.

7. **Completion rate** (in analytics):
   - `completionRate` = number of responses with `finished=true` / total responses
   - Expressed as a float between 0.0 and 1.0.

8. **Multiple choice stats** (in analytics):
   - For `multipleChoiceSingle` and `multipleChoiceMulti` questions: count how many responses selected each option.

9. **Rating stats** (in analytics):
   - For `rating` questions: return average rating and count per each possible value.

10. **Partial responses**: Responses with `finished=false` count toward `totalResponses` but NOT toward the numerator of `completionRate`.

11. **Person linking**: A response can optionally have a `personId`. If provided, the person must exist in the same environment. If the person doesn't exist, return `422`.

12. **Environment isolation**: All queries are scoped by `X-Environment-Id`. Data from one environment is completely invisible to another.

13. **Tag name uniqueness**: Within an environment, two tags cannot have the same name. Return `409 Conflict` on duplicate.

14. **Segment filters**: Segment filters define rules on people attributes. Filter format: `[{"attribute": "<attr_name>", "operator": "<op>", "value": "<val>"}]`. Operators: `equals`, `notEquals`, `contains`, `notContains`. Multiple filters are ANDed together. Filters are evaluated against people's `attributes` object.

15. **Cascade delete**: Deleting a survey deletes all its responses, questions, triggers, and tag associations. Deleting a person deletes all their responses. Deleting a tag removes all its survey associations.

16. **Webhook triggers**: Valid trigger events are: `responseCreated`, `responseFinished`, `surveyActivated`, `surveyCompleted`. Webhooks are not actually called (no HTTP callbacks needed), just stored and returned.
