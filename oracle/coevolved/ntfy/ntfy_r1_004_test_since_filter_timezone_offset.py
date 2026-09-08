import datetime as dt
import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def test_since_filter_timezone_offset():
    requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    topic = f"since-offset-{uuid.uuid4().hex}"

    created = requests.post(
        f"{BASE_URL}/api/topics/{topic}/messages",
        json={"message": "timezone offset since probe"},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert created.status_code == 201
    message = created.json()

    published = dt.datetime.fromisoformat(message["publishedAt"].replace("Z", "+00:00"))
    since_after_message = published + dt.timedelta(seconds=1)
    since_with_offset = since_after_message.astimezone(dt.timezone(dt.timedelta(hours=-12))).isoformat()

    listed = requests.get(
        f"{BASE_URL}/api/topics/{topic}/messages",
        params={"since": since_with_offset},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert listed.status_code == 200
    returned_ids = {item["id"] for item in listed.json()}
    assert message["id"] not in returned_ids
