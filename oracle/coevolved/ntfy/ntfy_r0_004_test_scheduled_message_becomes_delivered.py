import datetime as dt
import os
import time
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def iso_z(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def wait_until_after(moment, timeout_seconds=8):
    deadline = time.monotonic() + timeout_seconds
    while dt.datetime.now(dt.timezone.utc) <= moment:
        if time.monotonic() > deadline:
            raise AssertionError("scheduledAt target time was not reached before timeout")
        time.sleep(0.05)


def test_scheduled_message_becomes_delivered():
    unique = uuid.uuid4().hex
    topic = f"probe-due-scheduled-{unique}"
    message_text = f"due scheduled payload {unique}"
    scheduled_for = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=3)

    bootstrap = requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    assert bootstrap.status_code == 200

    published = requests.post(
        f"{BASE_URL}/api/topics/{topic}/messages",
        json={"message": message_text, "scheduledAt": iso_z(scheduled_for)},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert published.status_code == 201
    created = published.json()
    assert created["delivered"] is False

    immediate_list = requests.get(
        f"{BASE_URL}/api/topics/{topic}/messages",
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert immediate_list.status_code == 200
    assert all(message["id"] != created["id"] for message in immediate_list.json())

    wait_until_after(scheduled_for + dt.timedelta(milliseconds=250))

    delivered_list = requests.get(
        f"{BASE_URL}/api/topics/{topic}/messages",
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert delivered_list.status_code == 200
    delivered_matches = [message for message in delivered_list.json() if message["id"] == created["id"]]
    assert delivered_matches, "due scheduled message should appear in regular message list"
    assert delivered_matches[0]["delivered"] is True

    scheduled_list = requests.get(
        f"{BASE_URL}/api/topics/{topic}/messages/scheduled",
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert scheduled_list.status_code == 200
    assert all(message["id"] != created["id"] for message in scheduled_list.json())
