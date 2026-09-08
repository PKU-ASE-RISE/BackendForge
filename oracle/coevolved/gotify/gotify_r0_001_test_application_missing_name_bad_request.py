import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin-user"


def headers_for(key):
    return {"X-Gotify-Key": key, "Content-Type": "application/json"}


def ensure_admin():
    requests.get(f"{BASE_URL}/current/user", headers=headers_for(ADMIN_KEY), timeout=30)


def test_application_missing_name_bad_request():
    ensure_admin()
    key = f"missing-app-name-{uuid.uuid4().hex}"
    headers = headers_for(key)

    resp = requests.post(
        f"{BASE_URL}/applications",
        json={"description": "no name should be rejected"},
        headers=headers,
        timeout=30,
    )

    assert resp.status_code == 400
    data = resp.json()
    assert {"error", "errorCode", "errorDescription"}.issubset(data.keys())
    assert data["errorCode"] == 400

    list_resp = requests.get(f"{BASE_URL}/applications", headers=headers, timeout=30)
    assert list_resp.status_code == 200
    assert all(app["description"] != "no name should be rejected" for app in list_resp.json())
