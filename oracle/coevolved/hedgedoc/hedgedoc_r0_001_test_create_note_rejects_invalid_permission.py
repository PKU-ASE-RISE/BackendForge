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


def test_create_note_rejects_invalid_permission():
    _, headers = create_user()
    content = f"# Invalid Permission {uuid.uuid4().hex}\nBody"

    resp = requests.post(
        f"{API}/notes",
        json={"content": content, "permission": "workspace"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    list_resp = requests.get(f"{API}/notes", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert all(note["content"] != content for note in list_resp.json())
