import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def api_key(role, base_id, user=None):
    return f"{role}_{base_id}_{user or unique('user')}"


def h(key):
    return {"X-API-Key": key}


def test_base_update_forbids_api_key_base_mismatch():
    original_title = unique("original")
    create_resp = requests.post(
        f"{API}/bases",
        json={"title": original_title},
        headers=h(api_key("owner", "base1", "creator")),
    )
    assert create_resp.status_code == 201, create_resp.text
    base = create_resp.json()

    attempted_title = unique("intruder")
    wrong_base_key = api_key("owner", "notthisbase", "intruder")
    patch_resp = requests.patch(
        f"{API}/bases/{base['id']}",
        json={"title": attempted_title},
        headers=h(wrong_base_key),
    )

    assert patch_resp.status_code == 403, patch_resp.text

    reload_resp = requests.get(
        f"{API}/bases/{base['id']}",
        headers=h(api_key("owner", base["id"], "creator")),
    )
    assert reload_resp.status_code == 200, reload_resp.text
    assert reload_resp.json()["title"] == original_title
