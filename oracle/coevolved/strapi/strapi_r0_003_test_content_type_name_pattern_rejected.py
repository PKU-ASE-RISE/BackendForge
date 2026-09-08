import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def test_content_type_name_pattern_rejected():
    invalid_name = f"Bad-Name-{uuid.uuid4().hex[:8]}"
    resp = requests.post(
        f"{BASE_URL}/content-types",
        json={"name": invalid_name, "displayName": "Invalid Name"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["status"] == 400
