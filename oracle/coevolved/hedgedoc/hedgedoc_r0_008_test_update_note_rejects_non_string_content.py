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


def create_note(headers, content):
    resp = requests.post(f"{API}/notes", json={"content": content}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_update_note_rejects_non_string_content():
    _, headers = create_user()
    original_content = "# String Content\nThis should remain text"
    note = create_note(headers, original_content)

    update_resp = requests.put(
        f"{API}/notes/{note['id']}",
        json={"content": ["# Not a markdown string"]},
        headers=headers,
    )
    assert update_resp.status_code == 400, update_resp.text

    get_resp = requests.get(f"{API}/notes/{note['id']}", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["content"] == original_content
