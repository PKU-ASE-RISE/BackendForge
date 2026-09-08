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


def create_note(headers, content, permission="private"):
    resp = requests.post(
        f"{API}/notes",
        json={"content": content, "permission": permission},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_revision_update_records_previous_content():
    _, headers = create_user()
    original_content = "# Original Title\nFirst body"
    updated_content = "# Updated Title\nSecond body"
    note = create_note(headers, original_content)

    before_resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers)
    assert before_resp.status_code == 200, before_resp.text
    before_ids = {rev["id"] for rev in before_resp.json()}

    update_resp = requests.put(
        f"{API}/notes/{note['id']}",
        json={"content": updated_content},
        headers=headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["content"] == updated_content

    after_resp = requests.get(f"{API}/notes/{note['id']}/revisions", headers=headers)
    assert after_resp.status_code == 200, after_resp.text
    new_revisions = [rev for rev in after_resp.json() if rev["id"] not in before_ids]

    assert len(new_revisions) == 1
    new_revision = new_revisions[0]
    assert new_revision["content"] == original_content
    assert new_revision["title"] == "Original Title"
