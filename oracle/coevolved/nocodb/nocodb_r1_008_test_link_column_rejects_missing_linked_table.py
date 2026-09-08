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


def test_link_column_rejects_missing_linked_table():
    base = create_base()
    table_resp = requests.post(
        f"{API}/bases/{base['id']}/tables",
        json={"title": unique("table")},
        headers=h(owner_key(base["id"])),
    )
    assert table_resp.status_code == 201, table_resp.text
    table = table_resp.json()

    missing_table_id = unique("missing_table")
    resp = requests.post(
        f"{API}/bases/{base['id']}/tables/{table['id']}/columns",
        json={
            "title": unique("bad_link"),
            "type": "link",
            "options": {"linkedTableId": missing_table_id},
        },
        headers=h(owner_key(base["id"])),
    )
    assert resp.status_code == 400, resp.text
