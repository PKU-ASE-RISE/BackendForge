import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def test_prune_requires_older_than_seconds():
    requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    unique = uuid.uuid4().hex
    topic = f"prune-required-{unique}"
    message_text = f"message that must survive invalid prune {unique}"

    published = requests.post(
        f"{BASE_URL}/api/topics/{topic}/messages",
        json={"message": message_text},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert published.status_code == 201
    message_id = published.json()["id"]

    invalid_prune = requests.post(
        f"{BASE_URL}/api/admin/prune",
        json={},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert invalid_prune.status_code >= 400

    reloaded = requests.get(
        f"{BASE_URL}/api/messages/{message_id}",
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["message"] == message_text
