import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user():
    username = unique("note_alias_user")
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


def test_create_note_rejects_non_string_alias():
    headers = create_user()

    before = requests.get(f"{API}/notes", headers=headers)
    assert before.status_code == 200, before.text
    before_ids = {note["id"] for note in before.json()}

    resp = requests.post(
        f"{API}/notes",
        json={"content": "# Bad Alias\nbody", "alias": 12345},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    after = requests.get(f"{API}/notes", headers=headers)
    assert after.status_code == 200, after.text
    after_ids = {note["id"] for note in after.json()}
    assert after_ids == before_ids
