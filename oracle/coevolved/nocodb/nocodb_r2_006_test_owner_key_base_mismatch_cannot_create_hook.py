import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def h(api_key):
    return {"X-API-Key": api_key}


def owner_key(base_id):
    return f"owner_{base_id}_user_{uuid.uuid4().hex}"


def create_base():
    resp = requests.post(
        f"{API}/bases",
        json={"title": unique("base")},
        headers=h(owner_key("seed")),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_table(base_id):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables",
        json={"title": unique("table")},
        headers=h(owner_key(base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_owner_key_base_mismatch_cannot_create_hook():
    target_base = create_base()
    unrelated_base = create_base()
    table = create_table(target_base["id"])
    hook_title = unique("hook")

    create_with_wrong_base_key = requests.post(
        f"{API}/bases/{target_base['id']}/tables/{table['id']}/hooks",
        json={
            "title": hook_title,
            "event": "record.created",
            "url": f"https://example.com/{uuid.uuid4().hex}",
        },
        headers=h(owner_key(unrelated_base["id"])),
    )
    assert create_with_wrong_base_key.status_code == 403, create_with_wrong_base_key.text

    list_hooks = requests.get(
        f"{API}/bases/{target_base['id']}/tables/{table['id']}/hooks",
        headers=h(owner_key(target_base["id"])),
    )
    assert list_hooks.status_code == 200, list_hooks.text
    assert all(item["title"] != hook_title for item in list_hooks.json()["items"])
