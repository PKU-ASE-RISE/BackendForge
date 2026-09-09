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
    return f"owner_{base_id}_{uuid.uuid4().hex}"


def create_base():
    # Use delimiter-free key components; underscore parsing is unspecified
    # and unrelated to the behavior under test.
    resp = requests.post(
        f"{API}/bases",
        json={"title": unique("base")},
        headers=h(owner_key(uuid.uuid4().hex)),
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


def create_column(base_id, table_id, title, column_type):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables/{table_id}/columns",
        json={"title": title, "type": column_type},
        headers=h(owner_key(base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_record(base_id, table_id, payload):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables/{table_id}/records",
        json=payload,
        headers=h(owner_key(base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_deleted_column_removed_from_record_responses():
    base = create_base()
    table = create_table(base["id"])
    stale_title = unique("obsolete")
    kept_title = unique("kept")
    stale_col = create_column(base["id"], table["id"], stale_title, "text")
    create_column(base["id"], table["id"], kept_title, "text")

    marker = unique("value")
    kept_value = unique("still_there")
    record = create_record(
        base["id"],
        table["id"],
        {stale_title: marker, kept_title: kept_value},
    )

    delete_resp = requests.delete(
        f"{API}/bases/{base['id']}/tables/{table['id']}/columns/{stale_col['id']}",
        headers=h(owner_key(base["id"])),
    )
    assert delete_resp.status_code == 204, delete_resp.text

    reload_resp = requests.get(
        f"{API}/bases/{base['id']}/tables/{table['id']}/records/{record['id']}",
        headers=h(owner_key(base["id"])),
    )
    assert reload_resp.status_code == 200, reload_resp.text
    reloaded = reload_resp.json()
    assert reloaded[kept_title] == kept_value
    assert stale_title not in reloaded
