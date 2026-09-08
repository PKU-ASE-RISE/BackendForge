import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def test_publish_requires_message_field():
    requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    topic = f"missing-message-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/topics/{topic}/messages",
        json={"title": "missing required message"},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert response.status_code >= 400

    listed = requests.get(
        f"{BASE_URL}/api/topics/{topic}/messages",
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    if listed.status_code == 200:
        assert all(item.get("title") != "missing required message" for item in listed.json())
