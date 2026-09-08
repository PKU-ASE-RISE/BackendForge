import os
import uuid

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


def setup_bookable(api_key, user):
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
            "requiresConfirmation": False,
        },
        api_key=api_key,
    )
    assert event_resp.status_code == 201, event_resp.text
    return event_resp.json()


def test_malformed_booking_start_time_returns_400():
    user, api_key = create_user()
    event_type = setup_bookable(api_key, user)

    booking_resp = api(
        "post",
        "/v1/bookings",
        json_data={
            "eventTypeId": event_type["id"],
            "startTime": "not-a-date-time",
            "inviteeName": "Malformed Guest",
            "inviteeEmail": f"{unique('guest-')}@example.com",
        },
        api_key=api_key,
    )
    assert booking_resp.status_code == 400, booking_resp.text
