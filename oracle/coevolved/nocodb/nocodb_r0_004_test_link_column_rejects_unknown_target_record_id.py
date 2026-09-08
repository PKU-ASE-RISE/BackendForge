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


def create_table(base_id, title=None):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables",
        json={"title": title or unique("table")},
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


def test_link_column_rejects_unknown_target_record_id():
    base = create_base()
    orders = create_table(base["id"], unique("orders"))
    items = create_table(base["id"], unique("items"))
    create_column(base["id"], orders["id"], "itemLinks", "link", {"linkedTableId": items["id"]})

    fake_record_id = unique("missing_record")
    resp = requests.post(
        f"{API}/bases/{base['id']}/tables/{orders['id']}/records",
        json={"itemLinks": [fake_record_id]},
        headers=h(api_key("owner", base["id"])),
    )

    assert resp.status_code == 400, resp.text
    assert "error" in resp.json()

    records_resp = requests.get(
        f"{API}/bases/{base['id']}/tables/{orders['id']}/records",
        headers=h(api_key("owner", base["id"])),
    )
    assert records_resp.status_code == 200, records_resp.text
    assert all(fake_record_id not in record.get("itemLinks", []) for record in records_resp.json()["records"])
