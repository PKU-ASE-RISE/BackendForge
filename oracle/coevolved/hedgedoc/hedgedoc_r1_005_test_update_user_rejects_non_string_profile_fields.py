import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user():
    username = unique("profile_schema")
    resp = requests.post(
        f"{API}/users",
        json={
            "username": username,
            "displayName": "Valid Profile",
            "password": "testpass123",
            "photoUrl": "https://example.com/original.png",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data, {"X-API-Key": data["apiKey"]}


def test_update_user_rejects_non_string_profile_fields():
    user, headers = create_user()

    before = requests.get(f"{API}/users/{user['id']}", headers=headers)
    assert before.status_code == 200, before.text
    before_profile = before.json()

    resp = requests.put(
        f"{API}/users/{user['id']}",
        json={"displayName": {"bad": "name"}, "photoUrl": 12345},
        headers=headers,
    )
    assert resp.status_code == 400

    after = requests.get(f"{API}/users/{user['id']}", headers=headers)
    assert after.status_code == 200, after.text
    after_profile = after.json()
    assert after_profile["displayName"] == before_profile["displayName"]
    assert after_profile["photoUrl"] == before_profile["photoUrl"]
