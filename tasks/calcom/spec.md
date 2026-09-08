# Cal.com — Scheduling & Calendar Booking Platform

## Overview

Build a backend API for a scheduling and calendar booking platform similar to Cal.com. The platform allows users to define their availability, create bookable event types, and let others book time slots. It integrates with an external calendar service to check for conflicts and create events when bookings are confirmed.

## External Services

An external calendar service is available through the `CALENDAR_SERVICE_URL` environment variable. The evaluator sets this variable to the reachable service URL; use `http://localhost:9998` as the local-development fallback. This service simulates a connected calendar (like Google Calendar) and must be used for busy-time lookups and event creation upon booking.

## Authentication

All API endpoints require an `X-API-Key` header. If the header is missing or invalid, the API must respond with HTTP 401 Unauthorized.

API keys are created when a user is created. Any valid API key authenticates as that user.

## Core Concepts

### Users

Users are the primary entities who set up their scheduling profiles.

- Each user has a name, email, timezone (IANA format, e.g., "America/New_York"), and a default schedule
- Users receive an API key upon creation
- Users belong to zero or more teams

### Availability Schedules

Schedules define when a user is available for bookings.

- A schedule has a name, a timezone, and a set of weekly rules
- Weekly rules specify availability per day of week (e.g., Monday 09:00-12:00, 13:00-17:00)
- Date-specific overrides can mark specific dates as unavailable or set custom hours
- A user can have multiple schedules but one is their default

### Event Types

Event types define what can be booked.

- Each event type has: title, slug (URL-friendly identifier), description, duration (minutes), location options
- Constraints: bufferTimeBefore (minutes), bufferTimeAfter (minutes), minimumNotice (minutes), maxBookingsPerDay
- An event type belongs to a user or a team
- If `requiresConfirmation` is true, bookings start as "pending" and must be confirmed

### Bookings

Bookings represent scheduled appointments.

- A booking is created against an event type for a specific time slot
- Booking statuses: pending, confirmed, cancelled, rescheduled
- If the event type requires confirmation, new bookings are "pending" until the host confirms
- Otherwise, bookings are immediately "confirmed"
- When a booking is confirmed, an event is created in the host's connected external calendar
- When cancelled, the calendar event is removed
- Rescheduling creates a new booking and cancels the old one

### Teams

Teams allow collaborative scheduling.

- A team has members with roles (owner, admin, member)
- Team event types support scheduling strategies:
  - **Round Robin**: bookings rotate among available team members
  - **Collective**: all team members must be available (the slot must be free for everyone)

### Webhooks

Webhooks notify external systems of booking events.

- Users can register webhook URLs for specific event triggers
- Triggers: booking.created, booking.confirmed, booking.cancelled, booking.rescheduled
- When a trigger fires, a POST request is sent to the webhook URL with booking data
- The system should record webhook delivery attempts

### Available Slots

The slots endpoint is the core scheduling algorithm. Given an event type and a date range, it returns available time slots.

**Algorithm:**
1. Get the host user's availability schedule for the requested period
2. Generate potential slots based on the schedule rules (respecting the user's timezone)
3. Apply date-specific overrides (remove slots on unavailable dates, adjust for custom hours)
4. Remove slots that conflict with existing confirmed bookings (including buffer times)
5. Remove slots that conflict with external calendar busy times (fetched from mock service)
6. Remove slots within the minimum notice period (e.g., can't book within next 2 hours)
7. Remove slots if max bookings per day is reached for that day
8. For team event types:
   - Round Robin: a slot is available if ANY team member is free
   - Collective: a slot is available only if ALL team members are free
9. Return available slots as ISO 8601 timestamps

## Data Rules

- All timestamps in requests and responses are ISO 8601 with timezone (e.g., "2024-03-15T09:00:00Z")
- All field names use camelCase
- Storage starts empty — no seed data
- IDs are server-generated (UUIDs or auto-increment)

## Technical Requirements

- Framework/language: agent's choice
- The API must run on port 8000
- Must integrate with the external calendar service configured by `CALENDAR_SERVICE_URL`.
- Must handle timezone conversions correctly
