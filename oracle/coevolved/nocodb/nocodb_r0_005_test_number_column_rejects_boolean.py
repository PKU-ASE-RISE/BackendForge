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


def create_base():
    resp = requests.post(
        f"{API}/bases",
        json={"title": unique("base")},
        headers=h(api_key("owner", "base1")),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_table(base_id):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables",
        json={"title": unique("table")},
        headers=h(api_key("owner", base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_column(base_id, table_id, title, col_type, options=None):
    payload = {"title": title, "type": col_type}
    if options is not None:
        payload["options"] = options
    resp = requests.post(
        f"{API}/bases/{base_id}/tables/{table_id}/columns",
        json=payload,
        headers=h(api_key("owner", base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_number_column_rejects_boolean():
    base = create_base()
    table = create_table(base["id"])
    create_column(base["id"], table["id"], "quantity", "number")

    resp = requests.post(
        f"{API}/bases/{base['id']}/tables/{table['id']}/records",
        json={"quantity": True},
        headers=h(api_key("owner", base["id"])),
    )

    assert resp.status_code == 400, resp.text
    assert "error" in resp.json()

    records_resp = requests.get(
        f"{API}/bases/{base['id']}/tables/{table['id']}/records",
        headers=h(api_key("owner", base["id"])),
    )
    assert records_resp.status_code == 200, records_resp.text
    assert not any(record.get("quantity") is True for record in records_resp.json()["records"])
