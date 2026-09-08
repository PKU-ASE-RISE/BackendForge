"""
BackendForge — L2 Integration Tests for Cal.com Scheduling
Adversarial tests targeting common LLM implementation bugs.

"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def _u(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def api(method, path, json=None, params=None, api_key=None):
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    return requests.request(
        method,
        f"{BASE_URL}{path}",
        json=json,
        params=params,
        headers=headers,
        timeout=30,
    )


def create_user(name=None, tz="UTC"):
    email = f"{_u('u-')}@test.com"
    r = api("post", "/v1/users", json={"name": name or _u("User-"), "email": email, "timezone": tz})
    assert r.status_code == 201
    return r.json(), r.json()["apiKey"]


def create_schedule(key, tz="UTC", rules=None):
    if rules is None:
        rules = [{"dayOfWeek": i, "startTime": "09:00", "endTime": "17:00"} for i in range(5)]
    r = api("post", "/v1/schedules", json={"name": _u("sched-"), "timezone": tz, "weeklyRules": rules}, api_key=key)
    assert r.status_code == 201
    return r.json()


def setup_bookable(key, user_data, duration=30, confirms=False, **kw):
    """Full setup for booking: schedule + default + calendar + event type. Returns event type."""
    sched = create_schedule(key)
    default_resp = api("patch", f"/v1/users/{user_data['id']}", json={"defaultScheduleId": sched["id"]}, api_key=key)
    assert default_resp.status_code == 200, default_resp.text
    calendar_resp = api("post", "/v1/calendars", json={"name": "Cal"}, api_key=key)
    assert calendar_resp.status_code == 201, calendar_resp.text
    r = api("post", "/v1/event-types", json={
        "title": _u("evt-"),
        "slug": _u("slug-"),
        "duration": duration,
        "requiresConfirmation": confirms,
        **kw,
    }, api_key=key)
    assert r.status_code == 201
    return r.json()


def get_next_weekday(weekday):
    today = datetime.now(timezone.utc).date()
    days_ahead = weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def bookable_time():
    """Next Monday at 10:00 UTC."""
    monday = get_next_weekday(0)
    return datetime(monday.year, monday.month, monday.day, 10, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════
# L2 Tests
# ═══════════════════════════════════════════════════════════


class TestUserFields:
    """Pattern 1: User response fields."""

    def test_user_create_fields(self):
        r = api("post", "/v1/users", json={"name": "Alice", "email": f"{_u()}@t.com", "timezone": "America/New_York"})
        assert r.status_code == 201
        d = r.json()
        assert d["name"] == "Alice"
        assert d["timezone"] == "America/New_York"
        assert "id" in d
        assert "apiKey" in d
        assert "api_key" not in d

    def test_user_get(self):
        user, key = create_user("Bob")
        r = api("get", f"/v1/users/{user['id']}", api_key=key)
        assert r.status_code == 200
        assert r.json()["name"] == "Bob"


class TestScheduleFields:
    """Pattern 1+2: Schedule nested weeklyRules."""

    def test_schedule_create_with_rules(self):
        _, key = create_user()
        rules = [{"dayOfWeek": 0, "startTime": "09:00", "endTime": "12:00"}, {"dayOfWeek": 1, "startTime": "13:00", "endTime": "17:00"}]
        r = api("post", "/v1/schedules", json={"name": "Custom", "timezone": "UTC", "weeklyRules": rules}, api_key=key)
        assert r.status_code == 201
        d = r.json()
        assert d["name"] == "Custom"
        assert len(d["weeklyRules"]) == 2
        assert d["weeklyRules"][0]["dayOfWeek"] == 0
        assert d["weeklyRules"][0]["startTime"] == "09:00"
        assert "weekly_rules" not in d

    def test_schedule_get_roundtrip(self):
        _, key = create_user()
        sched = create_schedule(key, tz="Europe/London")
        r = api("get", f"/v1/schedules/{sched['id']}", api_key=key)
        assert r.status_code == 200
        assert r.json()["timezone"] == "Europe/London"
        assert len(r.json()["weeklyRules"]) == 5


class TestEventTypeFields:
    """Pattern 1: Event type fields."""

    def test_event_type_fields(self):
        _, key = create_user()
        slug = _u("et-")
        r = api("post", "/v1/event-types", json={
            "title": "Interview", "slug": slug, "duration": 60,
            "bufferTimeBefore": 15, "bufferTimeAfter": 10,
            "minimumNotice": 60, "maxBookingsPerDay": 3,
            "requiresConfirmation": True,
        }, api_key=key)
        assert r.status_code == 201
        d = r.json()
        assert d["title"] == "Interview"
        assert d["slug"] == slug
        assert d["duration"] == 60
        assert d["bufferTimeBefore"] == 15
        assert d["bufferTimeAfter"] == 10
        assert d["requiresConfirmation"] is True
        assert "id" in d
        assert "buffer_time_before" not in d


class TestBookingFields:
    """Pattern 1+5: Booking fields and auto-confirm."""

    def test_booking_auto_confirmed(self):
        user, key = create_user()
        et = setup_bookable(key, user, confirms=False)
        bt = bookable_time()
        r = api("post", "/v1/bookings", json={
            "eventTypeId": et["id"],
            "startTime": bt.isoformat(),
            "inviteeName": "Guest",
            "inviteeEmail": "g@t.com",
        }, api_key=key)
        assert r.status_code == 201
        d = r.json()
        assert d["status"] == "confirmed"
        assert d["inviteeName"] == "Guest"
        assert d["inviteeEmail"] == "g@t.com"
        assert "id" in d
        assert "startTime" in d
        assert "start_time" not in d
        assert "invitee_name" not in d

    def test_booking_pending_when_confirms_required(self):
        user, key = create_user()
        et = setup_bookable(key, user, confirms=True)
        bt = bookable_time()
        r = api("post", "/v1/bookings", json={
            "eventTypeId": et["id"],
            "startTime": bt.isoformat(),
            "inviteeName": "Pending",
            "inviteeEmail": "p@t.com",
        }, api_key=key)
        assert r.status_code == 201
        assert r.json()["status"] == "pending"


class TestSlotsEndpoint:
    """Pattern 3+5: Slots actually returns available times."""

    def test_slots_available_on_weekday(self):
        user, key = create_user()
        et = setup_bookable(key, user)
        monday = get_next_weekday(0)
        r = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": monday.isoformat(),
            "endDate": monday.isoformat(),
        }, api_key=key)
        assert r.status_code == 200
        slots = r.json()["slots"]
        assert len(slots) > 0

    def test_slots_empty_on_weekend(self):
        user, key = create_user()
        et = setup_bookable(key, user)
        saturday = get_next_weekday(5)
        r = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": saturday.isoformat(),
            "endDate": saturday.isoformat(),
        }, api_key=key)
        assert r.status_code == 200
        assert len(r.json()["slots"]) == 0


class TestCalendarConnect:
    """Pattern 1: Calendar connection."""

    def test_connect_calendar(self):
        _, key = create_user()
        r = api("post", "/v1/calendars", json={"name": "Google Cal"}, api_key=key)
        assert r.status_code == 201
        assert r.json()["name"] == "Google Cal"
        assert "id" in r.json()


class TestTeamFields:
    """Pattern 1: Team fields."""

    def test_team_create_and_get(self):
        _, key = create_user()
        r = api("post", "/v1/teams", json={"name": _u("team-"), "slug": _u("ts-")}, api_key=key)
        assert r.status_code == 201
        assert "id" in r.json()
        r = api("get", f"/v1/teams/{r.json()['id']}", api_key=key)
        assert r.status_code == 200


class TestWebhookFields:
    """Pattern 1+2: Webhook triggers array."""

    def test_webhook_create(self):
        _, key = create_user()
        r = api("post", "/v1/webhooks", json={"url": "https://hook.test/1", "triggers": ["booking.created", "booking.cancelled"]}, api_key=key)
        assert r.status_code == 201
        d = r.json()
        assert d["url"] == "https://hook.test/1"
        assert "booking.created" in d["triggers"]
        assert "id" in d


class TestStatusCodes:
    """Pattern 4: Status codes."""

    def test_create_201(self):
        r = api("post", "/v1/users", json={"name": _u(), "email": f"{_u()}@t.com", "timezone": "UTC"})
        assert r.status_code == 201

    def test_no_auth_401(self):
        r = api("get", "/v1/users")
        assert r.status_code == 401

    def test_not_found_404(self):
        _, key = create_user()
        r = api("get", f"/v1/schedules/{uuid.uuid4()}", api_key=key)
        assert r.status_code == 404


class TestBookingCancellation:
    """Pattern 5+7: Cancel changes status."""

    def test_cancel_booking(self):
        user, key = create_user()
        et = setup_bookable(key, user, confirms=False)
        bt = bookable_time() + timedelta(hours=2)
        r = api("post", "/v1/bookings", json={
            "eventTypeId": et["id"],
            "startTime": bt.isoformat(),
            "inviteeName": "C", "inviteeEmail": "c@t.com",
        }, api_key=key)
        assert r.status_code == 201, r.text
        bk_id = r.json()["id"]

        r = api("post", f"/v1/bookings/{bk_id}/cancel", api_key=key)
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"
