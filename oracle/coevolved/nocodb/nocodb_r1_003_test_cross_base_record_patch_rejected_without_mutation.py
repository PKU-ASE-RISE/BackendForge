import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def owner_key(base_id, user="user1"):
    return f"owner_{base_id}_{user}"


def h(api_key):
    return {"X-API-Key": api_key}


def create_base():
    resp = requests.post(
        f"{API}/bases",
        json={"title": unique("base")},
        headers=h(owner_key(uuid.uuid4().hex)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_cross_base_record_patch_rejected_without_mutation():
    base_a = create_base()
    base_b = create_base()
    assert base_a["id"] != base_b["id"], "Cross-base test requires distinct bases"
    key_a = owner_key(base_a["id"])
    key_b = owner_key(base_b["id"])

    table_resp = requests.post(
        f"{API}/bases/{base_a['id']}/tables",
        json={"title": unique("table")},
        headers=h(key_a),
    )
    assert table_resp.status_code == 201, table_resp.text
    table = table_resp.json()

    field = unique("name")
    col_resp = requests.post(
        f"{API}/bases/{base_a['id']}/tables/{table['id']}/columns",
        json={"title": field, "type": "text"},
        headers=h(key_a),
    )
    assert col_resp.status_code == 201, col_resp.text

    original_value = unique("original")
    rec_resp = requests.post(
        f"{API}/bases/{base_a['id']}/tables/{table['id']}/records",
        json={field: original_value},
        headers=h(key_a),
    )
    assert rec_resp.status_code == 201, rec_resp.text
    record = rec_resp.json()

    patch_resp = requests.patch(
        f"{API}/bases/{base_b['id']}/tables/{table['id']}/records/{record['id']}",
        json={field: unique("changed")},
        headers=h(key_b),
    )
    assert patch_resp.status_code in (403, 404), patch_resp.text

    get_resp = requests.get(
        f"{API}/bases/{base_a['id']}/tables/{table['id']}/records/{record['id']}",
        headers=h(key_a),
    )
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()[field] == original_value
