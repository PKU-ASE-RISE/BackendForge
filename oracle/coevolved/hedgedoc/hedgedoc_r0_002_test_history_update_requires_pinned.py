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


def create_note(headers):
    resp = requests.post(
        f"{API}/notes",
        json={"content": "# History Required Field\nBody"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_history_update_requires_pinned():
    _, headers = create_user()
    note = create_note(headers)

    read_resp = requests.get(f"{API}/notes/{note['id']}", headers=headers)
    assert read_resp.status_code == 200, read_resp.text

    update_resp = requests.put(
        f"{API}/me/history/{note['id']}",
        json={},
        headers=headers,
    )
    assert update_resp.status_code == 400, update_resp.text

    history_resp = requests.get(f"{API}/me/history", headers=headers)
    assert history_resp.status_code == 200, history_resp.text
    entry = next(item for item in history_resp.json() if item["noteId"] == note["id"])
    assert entry["pinned"] is False
