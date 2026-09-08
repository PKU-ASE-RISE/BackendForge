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


def test_missing_user_mutations_return_404():
    _, headers = create_user()
    missing_user_id = uuid.uuid4().hex

    update_resp = requests.put(
        f"{API}/users/{missing_user_id}",
        json={"displayName": "Nobody"},
        headers=headers,
    )
    assert update_resp.status_code == 404, update_resp.text

    delete_resp = requests.delete(f"{API}/users/{missing_user_id}", headers=headers)
    assert delete_resp.status_code == 404, delete_resp.text
