# Plausible — Privacy-First Web Analytics API

## Overview

Build a backend API for a privacy-first web analytics platform inspired by [Plausible Analytics](https://github.com/plausible/analytics). The platform enables website owners to register their sites, collect pageview and custom event data without cookies or personal data, and query rich analytics including real-time visitors, aggregate statistics, time series breakdowns, and conversion funnels.

## Core Concepts

### Sites
A **site** represents a website being tracked. Each site is identified by its domain (e.g., `example.com`). Sites belong to the API key holder and have configurable timezone and public dashboard settings.

### Events
An **event** is a recorded action on a tracked site. Events can be:
- **Pageviews**: automatic page visit recordings (`pageview` event name)
- **Custom Events**: named actions like `Signup`, `Download`, `Purchase`

Each event carries contextual data: URL, referrer, screen size, country, user agent.

### Sessions (Visits)
A **session** groups events from the same visitor within a time window. Visitor identity is determined by a hash of `domain + user_agent + country` (no cookies needed). Events from the same visitor within 30 minutes of each other belong to the same session.

### Goals
A **goal** defines a conversion target:
- **Pageview goal**: visitor reached a specific page (e.g., `/thank-you`)
- **Custom event goal**: visitor triggered a specific event (e.g., `Signup`)

### Funnels
A **funnel** is an ordered sequence of steps (goals) representing a desired user journey. The system tracks how many visitors complete each step, revealing drop-off points.

### Shared Links
Public URLs that grant read-only access to a site's dashboard, optionally protected by a password.

## Authentication

- **Management & Query endpoints**: Require `X-API-Key` header. Missing or invalid key returns `401 Unauthorized`.
- **Event ingestion endpoint**: Public (no authentication). The site is identified by the domain in the payload.

## Business Logic

### Visitor Identification
Visitors are identified by a deterministic hash of: `domain + user_agent + country`. This avoids cookies while still enabling unique visitor counting.

### Session Detection
Events from the same visitor (same hash) on the same site within **30 minutes** of each other are grouped into one session. A gap of more than 30 minutes starts a new session.

### Bounce Rate
A **bounce** is a session with exactly 1 pageview. Bounce rate = (single-pageview sessions / total sessions) * 100, expressed as a percentage (0-100).

### Visit Duration
Average time (in seconds) between the first and last event in a session. Sessions with only one event have duration 0. The average excludes or includes zero-duration sessions — the average is computed across all sessions.

### Unique Visitors
Count of distinct visitor hashes within the queried time period.

### Realtime Visitors
Count of distinct visitor hashes that have recorded at least one event in the last 5 minutes.

### Goal Conversion Rate
`(visitors who triggered the goal / total unique visitors in period) * 100`

### Funnel Analysis
For an N-step funnel:
- Step 1: count visitors who completed step 1
- Step 2: count visitors who completed step 2 AND also completed step 1
- Step N: count visitors who completed step N AND all previous steps

Steps are matched regardless of order in time — a visitor counts for step N if they completed all steps 1..N at any point during the period.

## Date Ranges

Queries support flexible date ranges:
- `period=day` — today only
- `period=7d` — last 7 days
- `period=30d` — last 30 days
- `period=month` — current calendar month
- `period=6mo` — last 6 months
- `period=12mo` — last 12 months
- `period=custom` with `dateFrom` and `dateTo` — arbitrary range

The `date` parameter sets the reference date (defaults to today). Format: `YYYY-MM-DD`.

## Filters

All stats/breakdown queries support filters to narrow results:
- `filters` query parameter as a JSON-encoded string
- Format: `{"property": "value"}` where property can be: `page`, `source`, `country`, `device`, `browser`, `os`, `eventName`
- Example: `filters={"country":"US","page":"/pricing"}`

## Endpoints Summary

### Sites (CRUD)
- Create, list, get, update, delete sites

### Event Ingestion
- Public POST endpoint to record events

### Realtime
- Current visitor count for a site

### Stats
- Aggregate stats (visitors, pageviews, bounce rate, visit duration, events)
- Time series (per-period breakdown)
- Breakdown by dimension (pages, sources, countries, devices, browsers, OS)

### Goals
- Create, list, delete goals for a site

### Funnels
- Create, list, get (with step-by-step data), delete funnels for a site

### Custom Properties
- Breakdown stats by custom event property

### Shared Links
- Create, list, delete shared links; access shared dashboard

### Export
- Export stats in structured JSON format

## Technical Requirements

- Storage starts empty — no seed data
- All JSON field names use camelCase
- Dates in `YYYY-MM-DD` format
- Timestamps in ISO 8601 format
- HTTP status codes: 200 (success), 201 (created), 204 (deleted), 400 (bad request), 401 (unauthorized), 404 (not found)
