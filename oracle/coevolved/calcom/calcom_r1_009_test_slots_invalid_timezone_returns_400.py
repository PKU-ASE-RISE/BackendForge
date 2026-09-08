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


def setup_event_type(api_key, user, target_date):
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
                    "endTime": "10:00",
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

    event_resp = api(
        "post",
        "/v1/event-types",
        json_data={
            "title": unique("evt-"),
            "slug": unique("slug-"),
            "duration": 60,
        },
        api_key=api_key,
    )
    assert event_resp.status_code == 201, event_resp.text
    return event_resp.json()


def test_slots_invalid_timezone_returns_400():
    user, api_key = create_user()
    target_date = datetime.now(timezone.utc).date() + timedelta(days=14)
    event_type = setup_event_type(api_key, user, target_date)

    slots_resp = api(
        "get",
        "/v1/slots/available",
        params={
            "eventTypeId": event_type["id"],
            "startDate": target_date.isoformat(),
            "endDate": target_date.isoformat(),
            "timezone": "Not/A_Real_Zone",
        },
        api_key=api_key,
    )
    assert slots_resp.status_code == 400, slots_resp.text
