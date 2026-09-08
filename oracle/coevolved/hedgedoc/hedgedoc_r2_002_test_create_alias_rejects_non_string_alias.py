import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v2"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def create_user():
    username = unique("alias_user")
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


def create_note(headers):
    alias = unique("primary")
    resp = requests.post(
        f"{API}/notes",
        json={"content": "# Alias Validation\nbody", "alias": alias},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_alias_rejects_non_string_alias():
    headers = create_user()
    note = create_note(headers)

    before = requests.get(f"{API}/notes/{note['id']}/aliases", headers=headers)
    assert before.status_code == 200, before.text
    before_aliases = before.json()

    resp = requests.post(
        f"{API}/notes/{note['id']}/aliases",
        json={"alias": ["not", "a", "slug"]},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    after = requests.get(f"{API}/notes/{note['id']}/aliases", headers=headers)
    assert after.status_code == 200, after.text
    assert after.json() == before_aliases
