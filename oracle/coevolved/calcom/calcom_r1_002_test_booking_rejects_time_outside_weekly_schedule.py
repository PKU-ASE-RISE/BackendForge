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


def setup_event_type_with_monday_schedule(api_key, user):
    sched_resp = api(
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
    assert sched_resp.status_code == 201, sched_resp.text

    default_resp = api(
        "patch",
        f"/v1/users/{user['id']}",
        json_data={"defaultScheduleId": sched_resp.json()["id"]},
        api_key=api_key,
    )
    assert default_resp.status_code == 200, default_resp.text

    cal_resp = api(
        "post",
        "/v1/calendars",
        json_data={"name": unique("cal-")},
        api_key=api_key,
    )
    assert cal_resp.status_code == 201, cal_resp.text

    event_resp = api(
        "post",
        "/v1/event-types",
        json_data={
            "title": unique("evt-"),
            "slug": unique("slug-"),
            "duration": 30,
        },
        api_key=api_key,
    )
    assert event_resp.status_code == 201, event_resp.text
    return event_resp.json()


def test_booking_rejects_time_outside_weekly_schedule():
    user, api_key = create_user()
    event_type = setup_event_type_with_monday_schedule(api_key, user)
    sunday = next_weekday(6)
    unavailable_start = datetime(
        sunday.year, sunday.month, sunday.day, 10, 0, tzinfo=timezone.utc
    )

    booking_resp = api(
        "post",
        "/v1/bookings",
        json_data={
            "eventTypeId": event_type["id"],
            "startTime": unavailable_start.isoformat(),
            "inviteeName": "Out Of Schedule",
            "inviteeEmail": f"{unique('guest-')}@example.com",
        },
        api_key=api_key,
    )
    assert booking_resp.status_code == 400, booking_resp.text
