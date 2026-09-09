import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user():
    username = unique("group_owner")
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


def test_add_group_member_rejects_missing_user():
    owner, headers = create_user()
    group_name = unique("grp")
    group_resp = requests.post(
        f"{API}/groups",
        json={"name": group_name, "displayName": "Team"},
        headers=headers,
    )
    assert group_resp.status_code == 201, group_resp.text
    group = group_resp.json()

    missing_user_id = unique("missing_user")
    resp = requests.post(
        f"{API}/groups/{group['id']}/members",
        json={"userId": missing_user_id},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text

    reloaded = requests.get(f"{API}/groups/{group['id']}", headers=headers)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["members"] == group["members"]
