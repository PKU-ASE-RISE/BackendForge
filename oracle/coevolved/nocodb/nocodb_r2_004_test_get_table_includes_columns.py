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


def test_get_table_includes_columns():
    base = create_base()
    table_resp = requests.post(
        f"{API}/bases/{base['id']}/tables",
        json={"title": unique("table")},
        headers=h(owner_key(base["id"])),
    )
    assert table_resp.status_code == 201, table_resp.text
    table = table_resp.json()

    first_col = requests.post(
        f"{API}/bases/{base['id']}/tables/{table['id']}/columns",
        json={"title": unique("first"), "type": "text"},
        headers=h(owner_key(base["id"])),
    )
    assert first_col.status_code == 201, first_col.text
    second_col = requests.post(
        f"{API}/bases/{base['id']}/tables/{table['id']}/columns",
        json={"title": unique("second"), "type": "number"},
        headers=h(owner_key(base["id"])),
    )
    assert second_col.status_code == 201, second_col.text

    get_resp = requests.get(
        f"{API}/bases/{base['id']}/tables/{table['id']}",
        headers=h(owner_key(base["id"])),
    )
    assert get_resp.status_code == 200, get_resp.text
    table_detail = get_resp.json()
    assert "columns" in table_detail
    returned_ids = {column["id"] for column in table_detail["columns"]}
    assert {first_col.json()["id"], second_col.json()["id"]}.issubset(returned_ids)
