import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user():
    username = unique("import_tags_user")
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


def test_import_note_rejects_invalid_tags():
    headers = create_user()
    marker = unique("badtag")

    before = requests.get(f"{API}/notes", headers=headers)
    assert before.status_code == 200, before.text
    before_ids = {note["id"] for note in before.json()}

    resp = requests.post(
        f"{API}/notes/import",
        json={"content": "# Imported\nbody", "tags": [marker, 42]},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    notes = requests.get(f"{API}/notes", headers=headers)
    assert notes.status_code == 200, notes.text
    after_ids = {note["id"] for note in notes.json()}
    assert after_ids == before_ids

    tags = requests.get(f"{API}/tags", headers=headers)
    assert tags.status_code == 200, tags.text
    assert marker not in tags.json()
