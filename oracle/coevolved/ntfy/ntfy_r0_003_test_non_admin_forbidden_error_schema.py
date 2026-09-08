import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"

ADMIN_HEADERS = {
    "X-User-Id": "admin-user",
    "X-Token": "admin-token",
    "Content-Type": "application/json",
}


def test_non_admin_forbidden_error_schema():
    unique = uuid.uuid4().hex
    username = f"probe-forbidden-{unique}"
    regular_headers = {
        "X-User-Id": username,
        "X-Token": f"token-{unique}",
        "Content-Type": "application/json",
    }

    bootstrap = requests.get(f"{BASE_URL}/api/topics", headers=ADMIN_HEADERS, timeout=30)
    assert bootstrap.status_code == 200

    created = requests.post(
        f"{BASE_URL}/api/users",
        json={"username": username, "admin": False},
        headers=ADMIN_HEADERS,
        timeout=30,
    )
    assert created.status_code == 201

    response = requests.get(f"{BASE_URL}/api/users", headers=regular_headers, timeout=30)

    assert response.status_code == 403
    data = response.json()
    assert data.get("code") == 403
    assert isinstance(data.get("error"), str) and data["error"]
    assert "detail" not in data
