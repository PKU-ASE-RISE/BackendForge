"""
BackendForge — L3 Workflow Tests for Cal.com Scheduling
Multi-step booking and availability workflows.

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
    r = api("post", "/v1/users", json={"name": name or _u("U-"), "email": email, "timezone": tz})
    assert r.status_code == 201
    return r.json(), r.json()["apiKey"]


def setup_bookable(key, user_data, duration=30, confirms=False, **kw):
    """Full setup: schedule (default), calendar, event type."""
    rules = [{"dayOfWeek": i, "startTime": "09:00", "endTime": "17:00"} for i in range(5)]
    r = api("post", "/v1/schedules", json={"name": "Work", "timezone": "UTC", "weeklyRules": rules}, api_key=key)
    assert r.status_code == 201, r.text
    sched_id = r.json()["id"]
    default_resp = api("patch", f"/v1/users/{user_data['id']}", json={"defaultScheduleId": sched_id}, api_key=key)
    assert default_resp.status_code == 200, default_resp.text
    calendar_resp = api("post", "/v1/calendars", json={"name": "Cal"}, api_key=key)
    assert calendar_resp.status_code == 201, calendar_resp.text
    r = api("post", "/v1/event-types", json={
        "title": _u("evt-"), "slug": _u("s-"), "duration": duration,
        "requiresConfirmation": confirms, **kw,
    }, api_key=key)
    assert r.status_code == 201
    return r.json()


def get_next_weekday(weekday):
    today = datetime.now(timezone.utc).date()
    days_ahead = weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def bookable_time(hour=10):
    monday = get_next_weekday(0)
    return datetime(monday.year, monday.month, monday.day, hour, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════
# L3 Tests — Workflows
# ═══════════════════════════════════════════════════════════


class TestBookingConfirmWorkflow:
    """Pending → confirm lifecycle."""

    def test_confirm_pending_booking(self):
        user, key = create_user()
        et = setup_bookable(key, user, confirms=True)
        bt = bookable_time()
        r = api("post", "/v1/bookings", json={
            "eventTypeId": et["id"], "startTime": bt.isoformat(),
            "inviteeName": "P", "inviteeEmail": "p@t.com",
        }, api_key=key)
        assert r.status_code == 201
        assert r.json()["status"] == "pending"
        bk_id = r.json()["id"]

        r = api("post", f"/v1/bookings/{bk_id}/confirm", api_key=key)
        assert r.status_code == 200
        assert r.json()["status"] == "confirmed"

        r = api("get", f"/v1/bookings/{bk_id}", api_key=key)
        assert r.json()["status"] == "confirmed"


class TestSlotConflictWorkflow:
    """Booking removes slot from availability."""

class TestCancelFreesSlot:
    """Cancel booking → slot available again."""

class TestRescheduleWorkflow:
    """Reschedule cancels old, creates new."""

class TestTeamWorkflow:
    """Team creation and member management."""

    def test_team_members(self):
        u1, k1 = create_user("Owner")
        u2, k2 = create_user("Member")

        r = api("post", "/v1/teams", json={"name": _u("team-"), "slug": _u("ts-")}, api_key=k1)
        assert r.status_code == 201
        team_id = r.json()["id"]

        r = api("post", f"/v1/teams/{team_id}/members", json={"userId": u2["id"], "role": "member"}, api_key=k1)
        assert r.status_code in [200, 201]

        r = api("get", f"/v1/teams/{team_id}/members", api_key=k1)
        assert r.status_code == 200
        assert len(r.json()) >= 1


class TestWebhookCRUD:
    """Webhook full lifecycle."""

    def test_webhook_create_list_delete(self):
        _, key = create_user()
        r = api("post", "/v1/webhooks", json={"url": "https://h.test/1", "triggers": ["booking.created"]}, api_key=key)
        assert r.status_code == 201
        wh_id = r.json()["id"]

        r = api("get", "/v1/webhooks", api_key=key)
        assert wh_id in [w["id"] for w in r.json()]

        r = api("delete", f"/v1/webhooks/{wh_id}", api_key=key)
        assert r.status_code in [200, 204]

        r = api("get", "/v1/webhooks", api_key=key)
        assert wh_id not in [w["id"] for w in r.json()]


class TestMultipleBookingsReduceSlots:
    """Multiple bookings progressively reduce availability."""

    def test_slots_decrease_with_bookings(self):
        user, key = create_user()
        et = setup_bookable(key, user, duration=60, confirms=False)
        monday = get_next_weekday(0)

        r = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": monday.isoformat(),
            "endDate": monday.isoformat(),
        }, api_key=key)
        initial = len(r.json()["slots"])
        assert initial > 0

        # Book 09:00
        first_booking_resp = api("post", "/v1/bookings", json={
            "eventTypeId": et["id"],
            "startTime": bookable_time(9).isoformat(),
            "inviteeName": "A", "inviteeEmail": "a@t.com",
        }, api_key=key)
        assert first_booking_resp.status_code == 201, first_booking_resp.text

        # Book 10:00
        second_booking_resp = api("post", "/v1/bookings", json={
            "eventTypeId": et["id"],
            "startTime": bookable_time(10).isoformat(),
            "inviteeName": "B", "inviteeEmail": "b@t.com",
        }, api_key=key)
        assert second_booking_resp.status_code == 201, second_booking_resp.text

        r = api("get", "/v1/slots/available", params={
            "eventTypeId": et["id"],
            "startDate": monday.isoformat(),
            "endDate": monday.isoformat(),
        }, api_key=key)
        after = len(r.json()["slots"])
        assert after < initial


class TestScheduleOverrideWorkflow:
    """Date override removes slots."""

    def test_override_blocks_day(self):
        user, key = create_user()
        rules = [{"dayOfWeek": i, "startTime": "09:00", "endTime": "17:00"} for i in range(5)]
        r = api("post", "/v1/schedules", json={"name": "W", "timezone": "UTC", "weeklyRules": rules}, api_key=key)
        assert r.status_code == 201, r.text
        sched_id = r.json()["id"]
        default_resp = api("patch", f"/v1/users/{user['id']}", json={"defaultScheduleId": sched_id}, api_key=key)
        assert default_resp.status_code == 200, default_resp.text
        calendar_resp = api("post", "/v1/calendars", json={"name": "C"}, api_key=key)
        assert calendar_resp.status_code == 201, calendar_resp.text
        r = api("post", "/v1/event-types", json={"title": _u(), "slug": _u("o-"), "duration": 30}, api_key=key)
        assert r.status_code == 201, r.text
        et_id = r.json()["id"]

        monday = get_next_weekday(0)
        # Has slots before
        r = api("get", "/v1/slots/available", params={"eventTypeId": et_id, "startDate": monday.isoformat(), "endDate": monday.isoformat()}, api_key=key)
        assert len(r.json()["slots"]) > 0

        # Override: unavailable
        r = api("post", f"/v1/schedules/{sched_id}/overrides", json={"date": monday.isoformat(), "available": False}, api_key=key)
        assert r.status_code in [200, 201]

        # No slots after override
        r = api("get", "/v1/slots/available", params={"eventTypeId": et_id, "startDate": monday.isoformat(), "endDate": monday.isoformat()}, api_key=key)
        assert len(r.json()["slots"]) == 0
