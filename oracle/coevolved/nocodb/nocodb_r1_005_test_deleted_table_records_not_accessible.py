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
        headers=h(owner_key("base1")),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_deleted_table_records_not_accessible():
    base = create_base()
    key = owner_key(base["id"])

    table_resp = requests.post(
        f"{API}/bases/{base['id']}/tables",
        json={"title": unique("table")},
        headers=h(key),
    )
    assert table_resp.status_code == 201, table_resp.text
    table = table_resp.json()

    field = unique("field")
    col_resp = requests.post(
        f"{API}/bases/{base['id']}/tables/{table['id']}/columns",
        json={"title": field, "type": "text"},
        headers=h(key),
    )
    assert col_resp.status_code == 201, col_resp.text

    rec_resp = requests.post(
        f"{API}/bases/{base['id']}/tables/{table['id']}/records",
        json={field: unique("value")},
        headers=h(key),
    )
    assert rec_resp.status_code == 201, rec_resp.text
    record = rec_resp.json()

    delete_resp = requests.delete(
        f"{API}/bases/{base['id']}/tables/{table['id']}",
        headers=h(key),
    )
    assert delete_resp.status_code == 204, delete_resp.text

    get_resp = requests.get(
        f"{API}/bases/{base['id']}/tables/{table['id']}/records/{record['id']}",
        headers=h(key),
    )
    assert get_resp.status_code == 404, get_resp.text
