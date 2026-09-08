import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin-user"


def headers_for(key):
    return {"X-Gotify-Key": key, "Content-Type": "application/json"}


def ensure_admin():
    requests.get(f"{BASE_URL}/current/user", headers=headers_for(ADMIN_KEY), timeout=30)


def test_message_create_with_application_token():
    ensure_admin()
    owner_key = f"app-token-owner-{uuid.uuid4().hex}"
    owner_headers = headers_for(owner_key)
    app_name = f"TokenApp-{uuid.uuid4().hex}"

    app_resp = requests.post(
        f"{BASE_URL}/applications",
        json={"name": app_name, "description": "token auth target", "defaultPriority": 2},
        headers=owner_headers,
        timeout=30,
    )
    assert app_resp.status_code == 200
    app = app_resp.json()
    app_id = app["id"]
    app_token = app["token"]

    message_text = f"created-with-token-{uuid.uuid4().hex}"
    create_resp = requests.post(
        f"{BASE_URL}/messages",
        json={"message": message_text, "title": "via app token", "priority": 4},
        headers=headers_for(app_token),
        timeout=30,
    )

    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["appid"] == app_id
    assert created["message"] == message_text
    assert created["title"] == "via app token"
    assert created["priority"] == 4

    list_resp = requests.get(
        f"{BASE_URL}/applications/{app_id}/messages",
        headers=owner_headers,
        timeout=30,
    )
    assert list_resp.status_code == 200
    messages = list_resp.json()["messages"]
    assert any(
        msg["id"] == created["id"] and msg["message"] == message_text
        for msg in messages
    )
