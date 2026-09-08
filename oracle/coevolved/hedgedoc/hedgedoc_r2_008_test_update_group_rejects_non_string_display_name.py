import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user():
    username = unique("group_update_user")
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


def test_update_group_rejects_non_string_display_name():
    headers = create_user()
    original_display = "Original Team"
    group_resp = requests.post(
        f"{API}/groups",
        json={"name": unique("grp"), "displayName": original_display},
        headers=headers,
    )
    assert group_resp.status_code == 201, group_resp.text
    group = group_resp.json()

    resp = requests.put(
        f"{API}/groups/{group['id']}",
        json={"displayName": {"not": "a string"}},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    reloaded = requests.get(f"{API}/groups/{group['id']}", headers=headers)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["displayName"] == original_display
