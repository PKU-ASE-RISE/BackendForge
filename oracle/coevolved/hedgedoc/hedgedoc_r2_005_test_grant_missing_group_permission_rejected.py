import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user():
    username = unique("perm_group_user")
    resp = requests.post(
        f"{API}/users",
        json={
            "username": username,
            "displayName": f"Display {username}",
            "password": "testpass123",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return {"X-API-Key": data["apiKey"]}


def create_limited_note(headers):
    resp = requests.post(
        f"{API}/notes",
        json={"content": "# Group Permission\nbody", "permission": "limited"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_grant_missing_group_permission_rejected():
    headers = create_user()
    note = create_limited_note(headers)

    before = requests.get(f"{API}/notes/{note['id']}/permissions", headers=headers)
    assert before.status_code == 200, before.text
    assert before.json()["groupPermissions"] == []

    missing_group_id = unique("missing_group")
    resp = requests.post(
        f"{API}/notes/{note['id']}/permissions/groups",
        json={"groupId": missing_group_id, "level": "read"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text

    after = requests.get(f"{API}/notes/{note['id']}/permissions", headers=headers)
    assert after.status_code == 200, after.text
    assert after.json()["groupPermissions"] == []
