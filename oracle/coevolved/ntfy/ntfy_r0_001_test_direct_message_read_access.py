import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def test_direct_message_read_access():
    unique = uuid.uuid4().hex
    topic = f"probe-private-{unique}"
    regular_username = f"probe-reader-{unique}"
    regular_headers = {
        "X-User-Id": regular_username,
        "X-Token": f"token-{unique}",
        "Content-Type": "application/json",
    }

    bootstrap = requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    assert bootstrap.status_code == 200

    users_before = requests.get(f"{BASE_URL}/api/users", headers=ADMIN_HEADERS, timeout=30)
    assert users_before.status_code == 200
    admin_user = next(user for user in users_before.json() if user["username"] == "admin-user")

    created_user = requests.post(
        f"{BASE_URL}/api/users",
        json={"username": regular_username, "admin": False},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert created_user.status_code == 201

    created_topic = requests.post(
        f"{BASE_URL}/api/topics",
        json={"name": topic, "description": "restricted direct-read probe"},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert created_topic.status_code == 201

    published = requests.post(
        f"{BASE_URL}/api/topics/{topic}/messages",
        json={"message": f"private payload {unique}", "title": "private"},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert published.status_code == 201
    message_id = published.json()["id"]

    restricted = requests.put(
        f"{BASE_URL}/api/topics/{topic}/access",
        json={"userId": admin_user["id"], "read": True, "write": True},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert restricted.status_code == 200

    list_response = requests.get(
        f"{BASE_URL}/api/topics/{topic}/messages",
        headers=regular_headers,
        timeout=30,
    )
    assert list_response.status_code == 403

    direct_response = requests.get(
        f"{BASE_URL}/api/messages/{message_id}",
        headers=regular_headers,
        timeout=30,
    )
    assert direct_response.status_code == 403
