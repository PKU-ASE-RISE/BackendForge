import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin-user"


def headers_for(key):
    return {"X-Gotify-Key": key, "Content-Type": "application/json"}


def ensure_admin():
    resp = requests.get(f"{BASE_URL}/current/user", headers=headers_for(ADMIN_KEY), timeout=30)
    assert resp.status_code == 200
    assert resp.json()["admin"] is True


def test_create_user_requires_pass():
    ensure_admin()
    user_name = f"missing-pass-{uuid.uuid4().hex}"

    resp = requests.post(
        f"{BASE_URL}/users",
        json={"name": user_name, "admin": False},
        headers=headers_for(ADMIN_KEY),
        timeout=30,
    )

    assert resp.status_code == 400
    data = resp.json()
    assert {"error", "errorCode", "errorDescription"}.issubset(data.keys())
    assert data["errorCode"] == 400

    users_resp = requests.get(f"{BASE_URL}/users", headers=headers_for(ADMIN_KEY), timeout=30)
    assert users_resp.status_code == 200
    assert all(user["name"] != user_name for user in users_resp.json())
