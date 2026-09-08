import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user():
    username = unique("user")
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
    return data, {"X-API-Key": data["apiKey"]}


def test_remove_missing_group_member_returns_404():
    owner, headers = create_user()
    group_resp = requests.post(
        f"{API}/groups",
        json={"name": unique("group"), "displayName": "Test Group"},
        headers=headers,
    )
    assert group_resp.status_code == 201, group_resp.text
    group = group_resp.json()
    missing_user_id = uuid.uuid4().hex

    delete_resp = requests.delete(
        f"{API}/groups/{group['id']}/members/{missing_user_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 404, delete_resp.text

    get_resp = requests.get(f"{API}/groups/{group['id']}", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["members"] == [owner["id"]]
