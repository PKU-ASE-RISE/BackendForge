import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {"X-Api-Key": "admin-user-key", "Content-Type": "application/json"}


def api(path, body=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if body is None else body,
        headers=ADMIN_HEADERS if headers is None else headers,
        timeout=30,
    )


def ensure_admin():
    response = api("/teams.info")
    assert response.status_code == 200, response.text


def create_member_user():
    member_key = f"invalid-role-member-{uuid.uuid4().hex}"
    member_headers = {"X-Api-Key": member_key, "Content-Type": "application/json"}
    response = api("/teams.info", headers=member_headers)
    assert response.status_code == 200, response.text

    listed = api("/users.list")
    assert listed.status_code == 200, listed.text
    for user in listed.json()["data"]:
        if user["name"] == member_key:
            return user
    raise AssertionError(f"member user {member_key} not found in users.list")


def test_users_update_rejects_invalid_role():
    ensure_admin()
    user = create_member_user()
    original_role = user["role"]

    response = api("/users.update", {"id": user["id"], "role": "owner"})

    assert response.status_code == 400, response.text

    reloaded = api("/users.info", {"id": user["id"]})
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["data"]["role"] == original_role
