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


def setup_notice_event_type(api_key, user, target_date):
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
                    "endTime": "17:00",
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
            "minimumNotice": 60 * 24 * 30,
        },
        api_key=api_key,
    )
    assert event_resp.status_code == 201, event_resp.text
    return event_resp.json()


def test_booking_rejects_before_minimum_notice():
    user, api_key = create_user()
    target_date = datetime.now(timezone.utc).date() + timedelta(days=14)
    event_type = setup_notice_event_type(api_key, user, target_date)
    target_start = datetime(
        target_date.year, target_date.month, target_date.day, 10, 0, tzinfo=timezone.utc
    )

    booking_resp = api(
        "post",
        "/v1/bookings",
        json_data={
            "eventTypeId": event_type["id"],
            "startTime": target_start.isoformat(),
            "inviteeName": "Too Soon",
            "inviteeEmail": f"{unique('guest-')}@example.com",
        },
        api_key=api_key,
    )
    assert booking_resp.status_code == 400, booking_resp.text
