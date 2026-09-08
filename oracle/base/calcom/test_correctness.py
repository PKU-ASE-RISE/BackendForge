"""
Comprehensive test suite for the Cal.com Scheduling API.
Tests correctness of all endpoints and business logic.
"""

import os
import time
import uuid
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
WEBHOOK_RECEIVER_URL = (
    os.environ.get("WEBHOOK_RECEIVER_URL")
    or "http://host.docker.internal:9998/webhooks"
)


# ============================================================
# Helper functions
# ============================================================

def api(method, path, json_data=None, params=None, api_key=None, headers=None):
    """Make an API request."""
    url = f"{BASE_URL}{path}"
    hdrs = dict(headers or {})
    if api_key:
        hdrs["X-API-Key"] = api_key
    resp = requests.request(
        method,
        url,
        json=json_data,
        params=params,
        headers=hdrs,
        timeout=30,
    )
    return resp


def create_user(name="Test User", email=None, timezone_str="UTC"):
    """Helper to create a user and return (user_data, api_key)."""
    if email is None:
        email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    resp = api("post", "/v1/users", json_data={
        "name": name,
        "email": email,
        "timezone": timezone_str,
    })
    assert resp.status_code == 201, f"Failed to create user: {resp.text}"
    data = resp.json()
    return data, data["apiKey"]


def create_schedule(api_key, name="Work Hours", tz="UTC", weekly_rules=None):
    """Helper to create a schedule."""
    if weekly_rules is None:
        # Mon-Fri 9:00-17:00
        weekly_rules = [
            {"dayOfWeek": i, "startTime": "09:00", "endTime": "17:00"}
            for i in range(5)  # 0=Mon to 4=Fri
        ]
    resp = api("post", "/v1/schedules", json_data={
        "name": name,
        "timezone": tz,
        "weeklyRules": weekly_rules,
    }, api_key=api_key)
    assert resp.status_code == 201, f"Failed to create schedule: {resp.text}"
    return resp.json()


def create_event_type(api_key, title="30min Meeting", slug=None, duration=30, **kwargs):
    """Helper to create an event type."""
    if slug is None:
        slug = f"meeting-{uuid.uuid4().hex[:8]}"
    data = {
        "title": title,
        "slug": slug,
        "duration": duration,
        **kwargs
    }
    resp = api("post", "/v1/event-types", json_data=data, api_key=api_key)
    assert resp.status_code == 201, f"Failed to create event type: {resp.text}"
    return resp.json()


def connect_calendar(api_key, name="My Calendar"):
    """Helper to connect a calendar."""
    resp = api("post", "/v1/calendars", json_data={"name": name}, api_key=api_key)
    assert resp.status_code == 201, f"Failed to connect calendar: {resp.text}"
    return resp.json()


def get_next_weekday(weekday, from_date=None):
    """Get the next occurrence of a weekday (0=Mon, 6=Sun) from given date."""
    if from_date is None:
        from_date = datetime.now(timezone.utc).date()
    days_ahead = weekday - from_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def get_next_monday():
    """Get next Monday's date."""
    return get_next_weekday(0)


# ============================================================
# Tests: Authentication
# ============================================================

class TestAuth:
    def test_missing_api_key_returns_401(self):
        """Requests without X-API-Key header should return 401."""
        resp = api("get", "/v1/users")
        assert resp.status_code == 401

    def test_invalid_api_key_returns_401(self):
        """Requests with invalid API key should return 401."""
        resp = api("get", "/v1/users", api_key=f"invalid-{uuid.uuid4()}")
        assert resp.status_code == 401

    def test_valid_api_key_works(self):
        """Requests with valid API key should succeed."""
        _, api_key = create_user()
        resp = api("get", "/v1/users", api_key=api_key)
        assert resp.status_code == 200

    def test_create_user_no_auth_required(self):
        """Creating a user should not require authentication."""
        resp = api("post", "/v1/users", json_data={
            "name": "No Auth User",
            "email": f"noauth-{uuid.uuid4().hex[:8]}@example.com",
            "timezone": "UTC",
        })
        assert resp.status_code == 201


# ============================================================
# Tests: Users
# ============================================================

class TestUsers:
    def test_create_user(self):
        user, api_key = create_user("Alice", timezone_str="America/New_York")
        assert user["name"] == "Alice"
        assert user["timezone"] == "America/New_York"
        assert "apiKey" in user
        assert "id" in user

    def test_create_user_duplicate_email(self):
        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        create_user(email=email)
        resp = api("post", "/v1/users", json_data={
            "name": "Duplicate",
            "email": email,
            "timezone": "UTC",
        })
        assert resp.status_code == 409

    def test_get_user(self):
        user, api_key = create_user("Bob")
        resp = api("get", f"/v1/users/{user['id']}", api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Bob"

    def test_get_user_not_found(self):
        _, api_key = create_user()
        resp = api("get", "/v1/users/nonexistent-id", api_key=api_key)
        assert resp.status_code == 404

    def test_update_user(self):
        user, api_key = create_user("Charlie")
        resp = api("patch", f"/v1/users/{user['id']}", json_data={
            "name": "Charlie Updated",
            "timezone": "Europe/London",
        }, api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Charlie Updated"
        assert resp.json()["timezone"] == "Europe/London"

    def test_delete_user(self):
        user, api_key = create_user("ToDelete")
        resp = api("delete", f"/v1/users/{user['id']}", api_key=api_key)
        assert resp.status_code == 204

    def test_get_current_user(self):
        user, api_key = create_user("CurrentUser")
        resp = api("get", "/v1/users/me", api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["id"] == user["id"]

    def test_list_users(self):
        _, api_key = create_user("Lister")
        resp = api("get", "/v1/users", api_key=api_key)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1


# ============================================================
# Tests: Schedules
# ============================================================

class TestSchedules:
    def test_create_schedule(self):
        _, api_key = create_user()
        schedule = create_schedule(api_key)
        assert schedule["name"] == "Work Hours"
        assert len(schedule["weeklyRules"]) == 5

    def test_list_schedules(self):
        _, api_key = create_user()
        create_schedule(api_key, name="Schedule A")
        create_schedule(api_key, name="Schedule B")
        resp = api("get", "/v1/schedules", api_key=api_key)
        assert resp.status_code == 200
        schedules = resp.json()
        assert len(schedules) >= 2

    def test_get_schedule(self):
        _, api_key = create_user()
        schedule = create_schedule(api_key)
        resp = api("get", f"/v1/schedules/{schedule['id']}", api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["id"] == schedule["id"]

    def test_update_schedule(self):
        _, api_key = create_user()
        schedule = create_schedule(api_key)
        resp = api("patch", f"/v1/schedules/{schedule['id']}", json_data={
            "name": "Updated Schedule",
            "weeklyRules": [
                {"dayOfWeek": 0, "startTime": "10:00", "endTime": "16:00"}
            ]
        }, api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Schedule"
        assert len(resp.json()["weeklyRules"]) == 1

    def test_delete_schedule(self):
        _, api_key = create_user()
        schedule = create_schedule(api_key)
        resp = api("delete", f"/v1/schedules/{schedule['id']}", api_key=api_key)
        assert resp.status_code == 204

    def test_add_date_override(self):
        _, api_key = create_user()
        schedule = create_schedule(api_key)
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        resp = api("post", f"/v1/schedules/{schedule['id']}/overrides", json_data={
            "date": future_date,
            "available": False,
        }, api_key=api_key)
        assert resp.status_code == 201

    def test_add_date_override_with_custom_hours(self):
        _, api_key = create_user()
        schedule = create_schedule(api_key)
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        resp = api("post", f"/v1/schedules/{schedule['id']}/overrides", json_data={
            "date": future_date,
            "available": True,
            "startTime": "10:00",
            "endTime": "14:00",
        }, api_key=api_key)
        assert resp.status_code == 201

    def test_list_date_overrides(self):
        _, api_key = create_user()
        schedule = create_schedule(api_key)
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        create_resp = api("post", f"/v1/schedules/{schedule['id']}/overrides", json_data={
            "date": future_date,
            "available": False,
        }, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        resp = api("get", f"/v1/schedules/{schedule['id']}/overrides", api_key=api_key)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_delete_date_override(self):
        _, api_key = create_user()
        schedule = create_schedule(api_key)
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        create_resp = api("post", f"/v1/schedules/{schedule['id']}/overrides", json_data={
            "date": future_date,
            "available": False,
        }, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        resp = api("delete", f"/v1/schedules/{schedule['id']}/overrides/{future_date}", api_key=api_key)
        assert resp.status_code == 204


# ============================================================
# Tests: Event Types
# ============================================================

class TestEventTypes:
    def test_create_event_type(self):
        _, api_key = create_user()
        et = create_event_type(api_key, title="Quick Call", duration=15)
        assert et["title"] == "Quick Call"
        assert et["duration"] == 15

    def test_create_event_type_with_constraints(self):
        _, api_key = create_user()
        et = create_event_type(api_key,
            title="Constrained",
            duration=30,
            bufferTimeBefore=15,
            bufferTimeAfter=10,
            minimumNotice=120,
            maxBookingsPerDay=3,
            requiresConfirmation=True,
        )
        assert et["bufferTimeBefore"] == 15
        assert et["bufferTimeAfter"] == 10
        assert et["minimumNotice"] == 120
        assert et["maxBookingsPerDay"] == 3
        assert et["requiresConfirmation"] is True

    def test_create_event_type_duplicate_slug(self):
        _, api_key = create_user()
        slug = f"dup-slug-{uuid.uuid4().hex[:8]}"
        create_event_type(api_key, slug=slug)
        resp = api("post", "/v1/event-types", json_data={
            "title": "Another",
            "slug": slug,
            "duration": 30,
        }, api_key=api_key)
        assert resp.status_code == 409

    def test_list_event_types(self):
        _, api_key = create_user()
        create_event_type(api_key, title="ET1")
        create_event_type(api_key, title="ET2")
        resp = api("get", "/v1/event-types", api_key=api_key)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_event_type(self):
        _, api_key = create_user()
        et = create_event_type(api_key)
        resp = api("get", f"/v1/event-types/{et['id']}", api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["id"] == et["id"]

    def test_update_event_type(self):
        _, api_key = create_user()
        et = create_event_type(api_key)
        resp = api("patch", f"/v1/event-types/{et['id']}", json_data={
            "title": "Updated Title",
            "duration": 45,
        }, api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"
        assert resp.json()["duration"] == 45

    def test_delete_event_type(self):
        _, api_key = create_user()
        et = create_event_type(api_key)
        resp = api("delete", f"/v1/event-types/{et['id']}", api_key=api_key)
        assert resp.status_code == 204


# ============================================================
# Tests: Bookings
# ============================================================

class TestBookings:
    def _setup_bookable(self, requires_confirmation=False):
        """Setup user, schedule, event type for booking."""
        user, api_key = create_user(timezone_str="UTC")
        schedule = create_schedule(api_key, tz="UTC")
        # Set as default schedule
        default_resp = api("patch", f"/v1/users/{user['id']}", json_data={
            "defaultScheduleId": schedule["id"]
        }, api_key=api_key)
        assert default_resp.status_code == 200, default_resp.text
        et = create_event_type(api_key, duration=30,
                               requiresConfirmation=requires_confirmation)
        return user, api_key, schedule, et

    def _get_bookable_time(self):
        """Get a future time that falls on a weekday during business hours."""
        next_mon = get_next_monday()
        # Book at 10:00 UTC on next Monday
        return datetime(next_mon.year, next_mon.month, next_mon.day, 10, 0, 0,
                       tzinfo=timezone.utc)

    def test_create_booking_auto_confirmed(self):
        user, api_key, schedule, et = self._setup_bookable(requires_confirmation=False)
        book_time = self._get_bookable_time()
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest User",
            "inviteeEmail": "guest@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201
        booking = resp.json()
        assert booking["status"] == "confirmed"
        assert booking["eventTypeId"] == et["id"]

    def test_create_booking_pending_confirmation(self):
        user, api_key, schedule, et = self._setup_bookable(requires_confirmation=True)
        book_time = self._get_bookable_time()
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest Pending",
            "inviteeEmail": "pending@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201
        booking = resp.json()
        assert booking["status"] == "pending"

    def test_confirm_booking(self):
        user, api_key, schedule, et = self._setup_bookable(requires_confirmation=True)
        book_time = self._get_bookable_time()
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest Confirm",
            "inviteeEmail": "confirm@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201, resp.text
        booking = resp.json()
        assert booking["status"] == "pending"

        # Confirm
        resp = api("post", f"/v1/bookings/{booking['id']}/confirm", api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

    def test_cancel_booking(self):
        user, api_key, schedule, et = self._setup_bookable()
        book_time = self._get_bookable_time()
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest Cancel",
            "inviteeEmail": "cancel@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201, resp.text
        booking = resp.json()

        resp = api("post", f"/v1/bookings/{booking['id']}/cancel", json_data={
            "reason": "Changed my mind"
        }, api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_already_cancelled(self):
        user, api_key, schedule, et = self._setup_bookable()
        book_time = self._get_bookable_time()
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest",
            "inviteeEmail": "cancel2@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201, resp.text
        booking = resp.json()
        first_cancel = api("post", f"/v1/bookings/{booking['id']}/cancel", api_key=api_key)
        assert first_cancel.status_code == 200, first_cancel.text
        resp = api("post", f"/v1/bookings/{booking['id']}/cancel", api_key=api_key)
        assert resp.status_code == 400

    def test_reschedule_booking(self):
        user, api_key, schedule, et = self._setup_bookable()
        book_time = self._get_bookable_time()
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest Reschedule",
            "inviteeEmail": "reschedule@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201, resp.text
        original_booking = resp.json()

        new_time = book_time + timedelta(hours=2)
        resp = api("post", f"/v1/bookings/{original_booking['id']}/reschedule", json_data={
            "newStartTime": new_time.isoformat(),
        }, api_key=api_key)
        assert resp.status_code == 200
        new_booking = resp.json()
        assert new_booking["status"] in ["confirmed", "pending"]
        assert new_booking["id"] != original_booking["id"]

        # Verify original is rescheduled
        resp = api("get", f"/v1/bookings/{original_booking['id']}", api_key=api_key)
        assert resp.json()["status"] == "rescheduled"

    def test_list_bookings(self):
        user, api_key, schedule, et = self._setup_bookable()
        book_time = self._get_bookable_time()
        create_resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest List",
            "inviteeEmail": "list@example.com",
        }, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        resp = api("get", "/v1/bookings", api_key=api_key)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_list_bookings_filter_status(self):
        user, api_key, schedule, et = self._setup_bookable()
        book_time = self._get_bookable_time()
        create_resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest",
            "inviteeEmail": "filter@example.com",
        }, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        resp = api("get", "/v1/bookings", params={"status": "confirmed"}, api_key=api_key)
        assert resp.status_code == 200
        for b in resp.json():
            assert b["status"] == "confirmed"

    def test_get_booking(self):
        user, api_key, schedule, et = self._setup_bookable()
        book_time = self._get_bookable_time()
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest Get",
            "inviteeEmail": "get@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201, resp.text
        booking = resp.json()
        resp = api("get", f"/v1/bookings/{booking['id']}", api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["id"] == booking["id"]

    def test_double_booking_conflict(self):
        """Cannot book the same slot twice."""
        user, api_key, schedule, et = self._setup_bookable()
        book_time = self._get_bookable_time()
        # First booking
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest 1",
            "inviteeEmail": "g1@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201

        # Second booking at same time
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest 2",
            "inviteeEmail": "g2@example.com",
        }, api_key=api_key)
        assert resp.status_code == 409


# ============================================================
# Tests: Available Slots
# ============================================================

class TestSlots:
    def _setup_for_slots(self, duration=30, tz="UTC", **et_kwargs):
        """Setup user with schedule and event type for slot queries."""
        user, api_key = create_user(timezone_str=tz)
        schedule = create_schedule(api_key, tz=tz)
        default_resp = api("patch", f"/v1/users/{user['id']}", json_data={
            "defaultScheduleId": schedule["id"]
        }, api_key=api_key)
        assert default_resp.status_code == 200, default_resp.text
        et = create_event_type(api_key, duration=duration, **et_kwargs)
        return user, api_key, schedule, et

    def test_basic_slot_availability(self):
        """Available slots should be returned within schedule hours."""
        user, api_key, schedule, et = self._setup_for_slots(duration=30)
        next_mon = get_next_monday()
        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        assert resp.status_code == 200
        slots = resp.json()["slots"]
        assert len(slots) > 0

        # Verify all slots are within 09:00-17:00 UTC
        for slot in slots:
            start = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(slot["end"].replace("Z", "+00:00"))
            assert start.hour >= 9
            assert end.hour <= 17
            assert (end - start).total_seconds() == 30 * 60

    def test_no_slots_on_weekend(self):
        """No slots on Saturday/Sunday when schedule is Mon-Fri."""
        user, api_key, schedule, et = self._setup_for_slots(duration=30)
        # Get next Saturday
        next_sat = get_next_weekday(5)
        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_sat.isoformat(),
            "endDate": next_sat.isoformat(),
        }, api_key=api_key)
        assert resp.status_code == 200
        slots = resp.json()["slots"]
        assert len(slots) == 0

    def test_slots_respect_existing_bookings(self):
        """Booked slots should not appear as available."""
        user, api_key, schedule, et = self._setup_for_slots(duration=30)
        next_mon = get_next_monday()
        book_time = datetime(next_mon.year, next_mon.month, next_mon.day, 10, 0, 0,
                           tzinfo=timezone.utc)

        # Book the 10:00 slot
        booking_resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Booked",
            "inviteeEmail": "booked@example.com",
        }, api_key=api_key)
        assert booking_resp.status_code == 201, booking_resp.text

        # Check slots
        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        slots = resp.json()["slots"]
        slot_starts = [s["start"] for s in slots]
        # The 10:00 slot should not be available
        for s in slot_starts:
            start_dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            assert not (start_dt.hour == 10 and start_dt.minute == 0)

    def test_buffer_time_blocks_adjacent_slots(self):
        """Buffer time before/after should block adjacent slots."""
        user, api_key, schedule, et = self._setup_for_slots(
            duration=30,
            bufferTimeBefore=15,
            bufferTimeAfter=15,
        )
        next_mon = get_next_monday()
        book_time = datetime(next_mon.year, next_mon.month, next_mon.day, 10, 0, 0,
                           tzinfo=timezone.utc)

        # Book 10:00-10:30
        booking_resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Buffer Test",
            "inviteeEmail": "buffer@example.com",
        }, api_key=api_key)
        assert booking_resp.status_code == 201, booking_resp.text

        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        slots = resp.json()["slots"]

        # The booking is 10:00-10:30. With 15min buffer before and after:
        # Buffer zone: 09:45-10:45
        # So 09:30-10:00 slot should be blocked (ends within buffer before)
        # and 10:30-11:00 slot should be blocked (starts within buffer after)
        for slot in slots:
            start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            # 09:30 slot blocked because of bufferBefore (booking at 10:00 needs 15min before = 09:45)
            assert not (start_dt.hour == 9 and start_dt.minute == 30)
            # 10:30 slot blocked because of bufferAfter (booking ends 10:30 + 15min = 10:45)
            assert not (start_dt.hour == 10 and start_dt.minute == 30)

    def test_minimum_notice(self):
        """Slots within minimum notice period should not be available."""
        user, api_key, schedule, et = self._setup_for_slots(
            duration=30,
            minimumNotice=120,  # 2 hours
        )
        today = datetime.now(timezone.utc).date()
        # If today is a weekday, check today; otherwise skip to next weekday
        if today.weekday() >= 5:
            target_date = get_next_monday()
        else:
            target_date = today

        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": target_date.isoformat(),
            "endDate": target_date.isoformat(),
        }, api_key=api_key)
        slots = resp.json()["slots"]
        now = datetime.now(timezone.utc)
        min_start = now + timedelta(minutes=120)

        for slot in slots:
            start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            assert start_dt >= min_start

    def test_max_bookings_per_day(self):
        """After reaching max bookings per day, no more slots for that day."""
        user, api_key, schedule, et = self._setup_for_slots(
            duration=30,
            maxBookingsPerDay=2,
        )
        next_mon = get_next_monday()

        # Book 2 slots
        for hour in [10, 11]:
            book_time = datetime(next_mon.year, next_mon.month, next_mon.day, hour, 0, 0,
                               tzinfo=timezone.utc)
            resp = api("post", "/v1/bookings", json_data={
                "eventTypeId": et["id"],
                "startTime": book_time.isoformat(),
                "inviteeName": f"Guest {hour}",
                "inviteeEmail": f"max{hour}@example.com",
            }, api_key=api_key)
            assert resp.status_code == 201

        # Check slots — should be empty for that day
        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        slots = resp.json()["slots"]
        assert len(slots) == 0

    def test_date_override_unavailable(self):
        """Date override marking a day unavailable should return no slots."""
        user, api_key, schedule, et = self._setup_for_slots(duration=30)
        next_mon = get_next_monday()

        # Add override for next Monday
        override_resp = api("post", f"/v1/schedules/{schedule['id']}/overrides", json_data={
            "date": next_mon.isoformat(),
            "available": False,
        }, api_key=api_key)
        assert override_resp.status_code == 201, override_resp.text

        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        slots = resp.json()["slots"]
        assert len(slots) == 0

    def test_date_override_custom_hours(self):
        """Date override with custom hours should return only those hours."""
        user, api_key, schedule, et = self._setup_for_slots(duration=30)
        next_mon = get_next_monday()

        # Override: only available 10:00-12:00 on that day
        override_resp = api("post", f"/v1/schedules/{schedule['id']}/overrides", json_data={
            "date": next_mon.isoformat(),
            "available": True,
            "startTime": "10:00",
            "endTime": "12:00",
        }, api_key=api_key)
        assert override_resp.status_code == 201, override_resp.text

        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        slots = resp.json()["slots"]
        assert len(slots) > 0

        for slot in slots:
            start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(slot["end"].replace("Z", "+00:00"))
            assert start_dt.hour >= 10
            assert end_dt.hour <= 12

    def test_timezone_conversion(self):
        """User in Asia/Tokyo, query slots — times should be correct."""
        user, api_key = create_user(timezone_str="Asia/Tokyo")
        # Schedule in Asia/Tokyo: Mon-Fri 09:00-17:00 Tokyo time
        schedule = create_schedule(api_key, tz="Asia/Tokyo")
        default_resp = api("patch", f"/v1/users/{user['id']}", json_data={
            "defaultScheduleId": schedule["id"]
        }, api_key=api_key)
        assert default_resp.status_code == 200, default_resp.text
        et = create_event_type(api_key, duration=60)

        next_mon = get_next_monday()
        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
            "timezone": "UTC",
        }, api_key=api_key)
        assert resp.status_code == 200
        slots = resp.json()["slots"]
        assert len(slots) > 0

        # Tokyo 09:00 = UTC 00:00, Tokyo 17:00 = UTC 08:00
        for slot in slots:
            start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            # Should be within UTC 00:00-08:00 (Tokyo 09:00-17:00)
            assert start_dt.hour >= 0
            assert start_dt.hour < 8

    def test_multi_day_range(self):
        """Query slots across multiple days."""
        user, api_key, schedule, et = self._setup_for_slots(duration=60)
        next_mon = get_next_monday()
        next_tue = next_mon + timedelta(days=1)

        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_tue.isoformat(),
        }, api_key=api_key)
        assert resp.status_code == 200
        slots = resp.json()["slots"]

        # Should have slots on both days
        days = set()
        for slot in slots:
            start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            days.add(start_dt.date())
        assert len(days) == 2


# ============================================================
# Tests: Teams
# ============================================================

class TestTeams:
    def test_create_team(self):
        _, api_key = create_user()
        resp = api("post", "/v1/teams", json_data={
            "name": "Engineering",
            "slug": f"engineering-{uuid.uuid4().hex[:8]}",
        }, api_key=api_key)
        assert resp.status_code == 201
        team = resp.json()
        assert team["name"] == "Engineering"
        assert "id" in team

    def test_list_teams(self):
        _, api_key = create_user()
        slug = f"team-{uuid.uuid4().hex[:8]}"
        create_resp = api("post", "/v1/teams", json_data={"name": "Team A", "slug": slug}, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        resp = api("get", "/v1/teams", api_key=api_key)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_team(self):
        _, api_key = create_user()
        slug = f"team-{uuid.uuid4().hex[:8]}"
        team_resp = api("post", "/v1/teams", json_data={"name": "Team B", "slug": slug}, api_key=api_key)
        assert team_resp.status_code == 201, team_resp.text
        team = team_resp.json()
        resp = api("get", f"/v1/teams/{team['id']}", api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["id"] == team["id"]

    def test_update_team(self):
        _, api_key = create_user()
        slug = f"team-{uuid.uuid4().hex[:8]}"
        team_resp = api("post", "/v1/teams", json_data={"name": "Old Name", "slug": slug}, api_key=api_key)
        assert team_resp.status_code == 201, team_resp.text
        team = team_resp.json()
        resp = api("patch", f"/v1/teams/{team['id']}", json_data={"name": "New Name"}, api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_team(self):
        _, api_key = create_user()
        slug = f"team-{uuid.uuid4().hex[:8]}"
        team_resp = api("post", "/v1/teams", json_data={"name": "Delete Me", "slug": slug}, api_key=api_key)
        assert team_resp.status_code == 201, team_resp.text
        team = team_resp.json()
        resp = api("delete", f"/v1/teams/{team['id']}", api_key=api_key)
        assert resp.status_code == 204

    def test_add_team_member(self):
        user1, api_key1 = create_user("Owner")
        user2, api_key2 = create_user("Member")
        slug = f"team-{uuid.uuid4().hex[:8]}"
        team_resp = api("post", "/v1/teams", json_data={"name": "Team C", "slug": slug}, api_key=api_key1)
        assert team_resp.status_code == 201, team_resp.text
        team = team_resp.json()

        resp = api("post", f"/v1/teams/{team['id']}/members", json_data={
            "userId": user2["id"],
            "role": "member",
        }, api_key=api_key1)
        assert resp.status_code == 201

    def test_list_team_members(self):
        user1, api_key1 = create_user("Owner2")
        user2, _ = create_user("Member2")
        slug = f"team-{uuid.uuid4().hex[:8]}"
        team_resp = api("post", "/v1/teams", json_data={"name": "Team D", "slug": slug}, api_key=api_key1)
        assert team_resp.status_code == 201, team_resp.text
        team = team_resp.json()
        member_resp = api("post", f"/v1/teams/{team['id']}/members", json_data={
            "userId": user2["id"],
            "role": "member",
        }, api_key=api_key1)
        assert member_resp.status_code == 201, member_resp.text

        resp = api("get", f"/v1/teams/{team['id']}/members", api_key=api_key1)
        assert resp.status_code == 200
        members = resp.json()
        assert len(members) >= 2  # owner + member

    def test_remove_team_member(self):
        user1, api_key1 = create_user("Owner3")
        user2, _ = create_user("Member3")
        slug = f"team-{uuid.uuid4().hex[:8]}"
        team_resp = api("post", "/v1/teams", json_data={"name": "Team E", "slug": slug}, api_key=api_key1)
        assert team_resp.status_code == 201, team_resp.text
        team = team_resp.json()
        member_resp = api("post", f"/v1/teams/{team['id']}/members", json_data={
            "userId": user2["id"],
            "role": "member",
        }, api_key=api_key1)
        assert member_resp.status_code == 201, member_resp.text

        resp = api("delete", f"/v1/teams/{team['id']}/members/{user2['id']}", api_key=api_key1)
        assert resp.status_code == 204

    def test_team_round_robin_scheduling(self):
        """Round-robin team event: bookings rotate among members."""
        user1, api_key1 = create_user("RR Host 1", timezone_str="UTC")
        user2, api_key2 = create_user("RR Host 2", timezone_str="UTC")

        # Create schedules for both
        s1 = create_schedule(api_key1, tz="UTC")
        s2 = create_schedule(api_key2, tz="UTC")
        default1_resp = api("patch", f"/v1/users/{user1['id']}", json_data={"defaultScheduleId": s1["id"]}, api_key=api_key1)
        assert default1_resp.status_code == 200, default1_resp.text
        default2_resp = api("patch", f"/v1/users/{user2['id']}", json_data={"defaultScheduleId": s2["id"]}, api_key=api_key2)
        assert default2_resp.status_code == 200, default2_resp.text

        # Create team
        slug = f"rr-team-{uuid.uuid4().hex[:8]}"
        team_resp = api("post", "/v1/teams", json_data={"name": "RR Team", "slug": slug}, api_key=api_key1)
        assert team_resp.status_code == 201, team_resp.text
        team = team_resp.json()
        member_resp = api("post", f"/v1/teams/{team['id']}/members", json_data={
            "userId": user2["id"], "role": "member"
        }, api_key=api_key1)
        assert member_resp.status_code == 201, member_resp.text

        # Create team event type with round robin
        et = create_event_type(api_key1, duration=30,
                              teamId=team["id"], schedulingStrategy="roundRobin")

        next_mon = get_next_monday()
        # Book two slots at different times
        time1 = datetime(next_mon.year, next_mon.month, next_mon.day, 10, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(next_mon.year, next_mon.month, next_mon.day, 11, 0, 0, tzinfo=timezone.utc)

        resp1 = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": time1.isoformat(),
            "inviteeName": "Guest A",
            "inviteeEmail": "a@example.com",
        }, api_key=api_key1)
        assert resp1.status_code == 201

        resp2 = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": time2.isoformat(),
            "inviteeName": "Guest B",
            "inviteeEmail": "b@example.com",
        }, api_key=api_key1)
        assert resp2.status_code == 201

        # Bookings should be assigned to different users (round-robin)
        b1 = resp1.json()
        b2 = resp2.json()
        assert b1["userId"] != b2["userId"]

    def test_team_collective_scheduling(self):
        """Collective team event: slot available only if ALL members free."""
        user1, api_key1 = create_user("Coll Host 1", timezone_str="UTC")
        user2, api_key2 = create_user("Coll Host 2", timezone_str="UTC")

        s1 = create_schedule(api_key1, tz="UTC")
        s2 = create_schedule(api_key2, tz="UTC")
        default1_resp = api("patch", f"/v1/users/{user1['id']}", json_data={"defaultScheduleId": s1["id"]}, api_key=api_key1)
        assert default1_resp.status_code == 200, default1_resp.text
        default2_resp = api("patch", f"/v1/users/{user2['id']}", json_data={"defaultScheduleId": s2["id"]}, api_key=api_key2)
        assert default2_resp.status_code == 200, default2_resp.text

        slug = f"coll-team-{uuid.uuid4().hex[:8]}"
        team_resp = api("post", "/v1/teams", json_data={"name": "Coll Team", "slug": slug}, api_key=api_key1)
        assert team_resp.status_code == 201, team_resp.text
        team = team_resp.json()
        member_resp = api("post", f"/v1/teams/{team['id']}/members", json_data={
            "userId": user2["id"], "role": "member"
        }, api_key=api_key1)
        assert member_resp.status_code == 201, member_resp.text

        # Create a personal event type for user2 and book them at 10:00
        personal_et = create_event_type(api_key2, duration=30)
        next_mon = get_next_monday()
        time_10 = datetime(next_mon.year, next_mon.month, next_mon.day, 10, 0, 0, tzinfo=timezone.utc)
        blocker_resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": personal_et["id"],
            "startTime": time_10.isoformat(),
            "inviteeName": "Blocker",
            "inviteeEmail": "blocker@example.com",
        }, api_key=api_key2)
        assert blocker_resp.status_code == 201, blocker_resp.text

        # Create collective team event type
        team_et = create_event_type(api_key1, duration=30,
                                   teamId=team["id"], schedulingStrategy="collective")

        # Check slots - 10:00 should NOT be available (user2 is busy)
        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": team_et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key1)
        slots = resp.json()["slots"]
        for slot in slots:
            start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            assert not (start_dt.hour == 10 and start_dt.minute == 0)


# ============================================================
# Tests: Calendars
# ============================================================

class TestCalendars:
    def test_connect_calendar(self):
        _, api_key = create_user()
        cal = connect_calendar(api_key)
        assert "id" in cal
        assert "externalCalendarId" in cal

    def test_list_calendar_connections(self):
        _, api_key = create_user()
        connect_calendar(api_key, "Cal 1")
        connect_calendar(api_key, "Cal 2")
        resp = api("get", "/v1/calendars", api_key=api_key)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_disconnect_calendar(self):
        _, api_key = create_user()
        cal = connect_calendar(api_key)
        resp = api("delete", f"/v1/calendars/{cal['id']}", api_key=api_key)
        assert resp.status_code == 204

# ============================================================
# Tests: Webhooks
# ============================================================

class TestWebhooks:
    def test_create_webhook(self):
        _, api_key = create_user()
        resp = api("post", "/v1/webhooks", json_data={
            "url": "https://example.com/webhook",
            "triggers": ["booking.created", "booking.cancelled"],
        }, api_key=api_key)
        assert resp.status_code == 201
        wh = resp.json()
        assert wh["url"] == "https://example.com/webhook"
        assert "booking.created" in wh["triggers"]
        assert wh["active"] is True

    def test_list_webhooks(self):
        _, api_key = create_user()
        create_resp = api("post", "/v1/webhooks", json_data={
            "url": "https://example.com/wh1",
            "triggers": ["booking.created"],
        }, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        resp = api("get", "/v1/webhooks", api_key=api_key)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_webhook(self):
        _, api_key = create_user()
        create_resp = api("post", "/v1/webhooks", json_data={
            "url": "https://example.com/wh2",
            "triggers": ["booking.confirmed"],
        }, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        wh = create_resp.json()
        resp = api("get", f"/v1/webhooks/{wh['id']}", api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["id"] == wh["id"]

    def test_update_webhook(self):
        _, api_key = create_user()
        create_resp = api("post", "/v1/webhooks", json_data={
            "url": "https://example.com/wh3",
            "triggers": ["booking.created"],
        }, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        wh = create_resp.json()
        resp = api("patch", f"/v1/webhooks/{wh['id']}", json_data={
            "url": "https://example.com/wh3-updated",
            "active": False,
        }, api_key=api_key)
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://example.com/wh3-updated"
        assert resp.json()["active"] is False

    def test_delete_webhook(self):
        _, api_key = create_user()
        create_resp = api("post", "/v1/webhooks", json_data={
            "url": "https://example.com/wh4",
            "triggers": ["booking.cancelled"],
        }, api_key=api_key)
        assert create_resp.status_code == 201, create_resp.text
        wh = create_resp.json()
        resp = api("delete", f"/v1/webhooks/{wh['id']}", api_key=api_key)
        assert resp.status_code == 204

    def test_webhook_delivery_recorded(self):
        """When a booking is created, webhook delivery should be recorded."""
        user, api_key = create_user(timezone_str="UTC")
        schedule = create_schedule(api_key, tz="UTC")
        default_resp = api("patch", f"/v1/users/{user['id']}", json_data={
            "defaultScheduleId": schedule["id"]
        }, api_key=api_key)
        assert default_resp.status_code == 200, default_resp.text
        et = create_event_type(api_key, duration=30)

        # Register webhook
        webhook_resp = api("post", "/v1/webhooks", json_data={
            "url": WEBHOOK_RECEIVER_URL,
            "triggers": ["booking.created"],
        }, api_key=api_key)
        assert webhook_resp.status_code == 201, webhook_resp.text
        wh = webhook_resp.json()

        # Create booking
        next_mon = get_next_monday()
        book_time = datetime(next_mon.year, next_mon.month, next_mon.day, 10, 0, 0,
                           tzinfo=timezone.utc)
        booking_resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "WH Guest",
            "inviteeEmail": "whguest@example.com",
        }, api_key=api_key)
        assert booking_resp.status_code == 201, booking_resp.text

        # Check deliveries - wait for async delivery to complete
        deliveries = []
        for _ in range(10):
            time.sleep(1)
            resp = api("get", f"/v1/webhooks/{wh['id']}/deliveries", api_key=api_key)
            assert resp.status_code == 200
            deliveries = resp.json()
            if len(deliveries) >= 1:
                break
        assert len(deliveries) >= 1
        assert deliveries[0]["trigger"] == "booking.created"


# ============================================================
# Tests: Edge Cases & Integration
# ============================================================

class TestEdgeCases:
    def test_booking_nonexistent_event_type(self):
        _, api_key = create_user()
        next_mon = get_next_monday()
        start_time = datetime(
            next_mon.year, next_mon.month, next_mon.day, 10, 0, tzinfo=timezone.utc
        )
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": "nonexistent",
            "startTime": start_time.isoformat(),
            "inviteeName": "Guest",
            "inviteeEmail": "guest@example.com",
        }, api_key=api_key)
        assert resp.status_code in [400, 404]

    def test_slots_nonexistent_event_type(self):
        _, api_key = create_user()
        next_mon = get_next_monday()
        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": "nonexistent",
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        assert resp.status_code == 404

    def test_confirm_non_pending_booking(self):
        """Confirming a booking that's not pending should fail."""
        user, api_key = create_user(timezone_str="UTC")
        schedule = create_schedule(api_key, tz="UTC")
        default_resp = api("patch", f"/v1/users/{user['id']}", json_data={
            "defaultScheduleId": schedule["id"]
        }, api_key=api_key)
        assert default_resp.status_code == 200, default_resp.text
        et = create_event_type(api_key, duration=30, requiresConfirmation=False)

        next_mon = get_next_monday()
        book_time = datetime(next_mon.year, next_mon.month, next_mon.day, 10, 0, 0,
                           tzinfo=timezone.utc)
        resp = api("post", "/v1/bookings", json_data={
            "eventTypeId": et["id"],
            "startTime": book_time.isoformat(),
            "inviteeName": "Guest",
            "inviteeEmail": "guest@example.com",
        }, api_key=api_key)
        assert resp.status_code == 201, resp.text
        booking = resp.json()
        assert booking["status"] == "confirmed"

        # Try to confirm again
        resp = api("post", f"/v1/bookings/{booking['id']}/confirm", api_key=api_key)
        assert resp.status_code == 400

    def test_slot_duration_alignment(self):
        """Slots should be aligned to the event type duration."""
        user, api_key, schedule, et = TestSlots()._setup_for_slots(duration=60)
        next_mon = get_next_monday()
        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        slots = resp.json()["slots"]
        for slot in slots:
            start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(slot["end"].replace("Z", "+00:00"))
            assert (end_dt - start_dt).total_seconds() == 60 * 60  # 60 min duration

    def test_set_default_schedule(self):
        """User's default schedule is used for slot calculation."""
        user, api_key = create_user(timezone_str="UTC")
        # Create two schedules with different hours
        s1 = create_schedule(api_key, name="Short Day", tz="UTC", weekly_rules=[
            {"dayOfWeek": i, "startTime": "09:00", "endTime": "12:00"} for i in range(5)
        ])
        s2 = create_schedule(api_key, name="Long Day", tz="UTC", weekly_rules=[
            {"dayOfWeek": i, "startTime": "08:00", "endTime": "20:00"} for i in range(5)
        ])

        # Set s1 as default
        api("patch", f"/v1/users/{user['id']}", json_data={
            "defaultScheduleId": s1["id"]
        }, api_key=api_key)

        et = create_event_type(api_key, duration=60)
        next_mon = get_next_monday()

        resp = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": next_mon.isoformat(),
            "endDate": next_mon.isoformat(),
        }, api_key=api_key)
        slots = resp.json()["slots"]

        # All slots should be within 09:00-12:00
        for slot in slots:
            start_dt = datetime.fromisoformat(slot["start"].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(slot["end"].replace("Z", "+00:00"))
            assert start_dt.hour >= 9
            assert end_dt.hour <= 12
