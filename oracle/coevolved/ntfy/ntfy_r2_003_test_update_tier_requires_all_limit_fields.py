import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def test_update_tier_requires_all_limit_fields():
    requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    unique = uuid.uuid4().hex
    original_name = f"tier-full-put-{unique}"
    changed_name = f"tier-partial-put-{unique}"

    created = requests.post(
        f"{BASE_URL}/api/tiers",
        json={
            "name": original_name,
            "messagesPerDay": 20,
            "messagesPerMinute": 5,
        },
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert created.status_code == 201
    tier_id = created.json()["id"]

    partial_update = requests.put(
        f"{BASE_URL}/api/tiers/{tier_id}",
        json={"name": changed_name},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert partial_update.status_code >= 400

    listed = requests.get(f"{BASE_URL}/api/tiers", headers=ADMIN_HEADERS, timeout=30)
    assert listed.status_code == 200
    tier = next(item for item in listed.json() if item["id"] == tier_id)
    assert tier["name"] == original_name
    assert tier["messagesPerDay"] == 20
    assert tier["messagesPerMinute"] == 5
