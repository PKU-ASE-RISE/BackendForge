import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def test_create_tier_requires_limit_fields():
    requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    tier_name = f"missing-limits-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/tiers",
        json={"name": tier_name},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert 400 <= response.status_code < 500

    listed = requests.get(f"{BASE_URL}/api/tiers", headers=ADMIN_HEADERS, timeout=30)
    assert listed.status_code == 200
    assert all(tier["name"] != tier_name for tier in listed.json())
