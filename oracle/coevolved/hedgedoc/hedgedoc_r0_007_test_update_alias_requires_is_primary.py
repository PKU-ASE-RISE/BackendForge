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


def test_update_alias_requires_is_primary():
    _, headers = create_user()
    initial_alias = unique("primary")
    secondary_alias = unique("secondary")

    note_resp = requests.post(
        f"{API}/notes",
        json={"content": "# Alias Required Field\nBody", "alias": initial_alias},
        headers=headers,
    )
    assert note_resp.status_code == 201, note_resp.text
    note = note_resp.json()

    alias_resp = requests.post(
        f"{API}/notes/{note['id']}/aliases",
        json={"alias": secondary_alias},
        headers=headers,
    )
    assert alias_resp.status_code == 201, alias_resp.text

    update_resp = requests.put(
        f"{API}/aliases/{secondary_alias}",
        json={},
        headers=headers,
    )
    assert update_resp.status_code == 400, update_resp.text

    aliases_resp = requests.get(f"{API}/notes/{note['id']}/aliases", headers=headers)
    assert aliases_resp.status_code == 200, aliases_resp.text
    alias_state = {item["alias"]: item["isPrimary"] for item in aliases_resp.json()}
    assert alias_state[initial_alias] is True
    assert alias_state[secondary_alias] is False
