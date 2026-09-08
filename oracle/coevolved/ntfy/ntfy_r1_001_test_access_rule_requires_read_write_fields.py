import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def _user_headers(username):
    return {
        "X-User-Id": username,
        "X-Token": f"token-{username}",
        "Content-Type": "application/json",
    }


def test_access_rule_requires_read_write_fields():
    requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    suffix = uuid.uuid4().hex
    topic = f"access-required-{suffix}"
    target_username = f"access-target-{suffix}"
    target_headers = _user_headers(target_username)

    create_topic = requests.post(
        f"{BASE_URL}/api/topics",
        json={"name": topic},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert create_topic.status_code == 201

    auto_create_user = requests.get(f"{BASE_URL}/api/topics", headers=target_headers, timeout=30)
    assert auto_create_user.status_code == 200
    users = requests.get(f"{BASE_URL}/api/users", headers=ADMIN_HEADERS, timeout=30)
    assert users.status_code == 200
    target_user = next(user for user in users.json() if user["username"] == target_username)

    response = requests.put(
        f"{BASE_URL}/api/topics/{topic}/access",
        json={"userId": target_user["id"]},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert response.status_code >= 400

    rules = requests.get(f"{BASE_URL}/api/topics/{topic}/access", headers=ADMIN_HEADERS, timeout=30)
    assert rules.status_code == 200
    assert all(rule["userId"] != target_user["id"] for rule in rules.json())
