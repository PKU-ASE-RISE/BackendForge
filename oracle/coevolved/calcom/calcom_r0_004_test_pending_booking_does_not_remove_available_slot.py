import os
import uuid
from datetime import datetime, timedelta, timezone

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def api(method, path, json_data=None, params=None, api_key=None):
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    return getattr(requests, method)(
        f"{BASE_URL}{path}",
        json=json_data,
        params=params,
        headers=headers,
        timeout=30,
    )


def unique(prefix):
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def parse_dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def slot_start_set(slots_body):
    return {parse_dt(slot["start"]) for slot in slots_body["slots"]}


def next_weekday(weekday):
    today = datetime.now(timezone.utc).date()
    days_ahead = weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def create_user():
    resp = api(
        "post",
        "/v1/users",
        json_data={
            "name": unique("user-"),
            "email": f"{unique('u-')}@example.com",
            "timezone": "UTC",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body, body["apiKey"]


def setup_confirmation_event_type(api_key, user):
    schedule_resp = api(
        "post",
        "/v1/schedules",
        json_data={
            "name": unique("sched-"),
            "timezone": "UTC",
            "weeklyRules": [
                {"dayOfWeek": 0, "startTime": "09:00", "endTime": "17:00"}
            ],
        },
        api_key=api_key,
    )
    assert schedule_resp.status_code == 201, schedule_resp.text
    schedule_id = schedule_resp.json()["id"]

    patch_resp = api(
        "patch",
        f"/v1/users/{user['id']}",
        json_data={"defaultScheduleId": schedule_id},
        api_key=api_key,
    )
    assert patch_resp.status_code == 200, patch_resp.text

    calendar_resp = api(
        "post",
        "/v1/calendars",
        json_data={"name": unique("cal-")},
        api_key=api_key,
    )
    assert calendar_resp.status_code == 201, calendar_resp.text

    event_resp = api(
        "post",
        "/v1/event-types",
        json_data={
            "title": unique("evt-"),
            "slug": unique("slug-"),
            "duration": 30,
            "requiresConfirmation": True,
        },
        api_key=api_key,
    )
    assert event_resp.status_code == 201, event_resp.text
    return event_resp.json()


def test_pending_booking_does_not_remove_available_slot():
    user, api_key = create_user()
    event_type = setup_confirmation_event_type(api_key, user)
    monday = next_weekday(0)
    target_start = datetime(
        monday.year, monday.month, monday.day, 10, 0, tzinfo=timezone.utc
    )
    slot_params = {
        "eventTypeId": event_type["id"],
        "startDate": monday.isoformat(),
        "endDate": monday.isoformat(),
    }

    initial_resp = api(
        "get", "/v1/slots/available", params=slot_params, api_key=api_key
    )
    assert initial_resp.status_code == 200, initial_resp.text
    assert target_start in slot_start_set(initial_resp.json())

    booking_resp = api(
        "post",
        "/v1/bookings",
        json_data={
            "eventTypeId": event_type["id"],
            "startTime": target_start.isoformat(),
            "inviteeName": "Pending Guest",
            "inviteeEmail": f"{unique('guest-')}@example.com",
        },
        api_key=api_key,
    )
    assert booking_resp.status_code == 201, booking_resp.text
    assert booking_resp.json()["status"] == "pending"

    after_resp = api(
        "get", "/v1/slots/available", params=slot_params, api_key=api_key
    )
    assert after_resp.status_code == 200, after_resp.text
    assert target_start in slot_start_set(after_resp.json())
