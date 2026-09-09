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


def test_cross_base_share_delete_rejected_without_side_effect():
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

    rec_resp = requests.post(
        f"{API}/bases/{base_a['id']}/tables/{table['id']}/records",
        json={field: unique("public")},
        headers=h(key_a),
    )
    assert rec_resp.status_code == 201, rec_resp.text

    view_resp = requests.post(
        f"{API}/bases/{base_a['id']}/tables/{table['id']}/views",
        json={"title": unique("view"), "type": "grid"},
        headers=h(key_a),
    )
    assert view_resp.status_code == 201, view_resp.text
    view = view_resp.json()

    share_resp = requests.post(
        f"{API}/bases/{base_a['id']}/tables/{table['id']}/views/{view['id']}/shares",
        json={},
        headers=h(key_a),
    )
    assert share_resp.status_code == 201, share_resp.text
    share = share_resp.json()

    before_resp = requests.get(f"{API}/shared/{share['uuid']}/records")
    assert before_resp.status_code == 200, before_resp.text

    delete_resp = requests.delete(
        f"{API}/bases/{base_b['id']}/tables/{table['id']}/views/{view['id']}/shares/{share['id']}",
        headers=h(key_b),
    )
    assert delete_resp.status_code in (403, 404), delete_resp.text

    after_resp = requests.get(f"{API}/shared/{share['uuid']}/records")
    assert after_resp.status_code == 200, after_resp.text
