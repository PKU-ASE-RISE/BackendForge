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


def future_date(days=14):
    return datetime.now(timezone.utc).date() + timedelta(days=days)


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


def setup_limited_event_type(api_key, user, target_date):
    sched_resp = api(
        "post",
        "/v1/schedules",
        json_data={
            "name": unique("sched-"),
            "timezone": "UTC",
            "weeklyRules": [
                {
                    "dayOfWeek": target_date.weekday(),
                    "startTime": "09:00",
                    "endTime": "12:00",
                }
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
            "maxBookingsPerDay": 1,
        },
        api_key=api_key,
    )
    assert event_resp.status_code == 201, event_resp.text
    return event_resp.json()


def make_booking(api_key, event_type_id, start_time, guest_prefix):
    return api(
        "post",
        "/v1/bookings",
        json_data={
            "eventTypeId": event_type_id,
            "startTime": start_time.isoformat(),
            "inviteeName": guest_prefix,
            "inviteeEmail": f"{unique('guest-')}@example.com",
        },
        api_key=api_key,
    )


def test_booking_rejects_when_max_bookings_per_day_reached():
    user, api_key = create_user()
    target_date = future_date()
    event_type = setup_limited_event_type(api_key, user, target_date)

    first_start = datetime(
        target_date.year, target_date.month, target_date.day, 9, 0, tzinfo=timezone.utc
    )
    second_start = datetime(
        target_date.year, target_date.month, target_date.day, 10, 0, tzinfo=timezone.utc
    )

    first_resp = make_booking(api_key, event_type["id"], first_start, "First Guest")
    assert first_resp.status_code == 201, first_resp.text
    assert first_resp.json()["status"] == "confirmed"

    second_resp = make_booking(api_key, event_type["id"], second_start, "Second Guest")
    assert second_resp.status_code == 400, second_resp.text

    listed_resp = api(
        "get",
        "/v1/bookings",
        params={"eventTypeId": event_type["id"]},
        api_key=api_key,
    )
    assert listed_resp.status_code == 200, listed_resp.text
    assert len(listed_resp.json()) == 1
