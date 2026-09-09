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


def create_column(base_id, table_id, title):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables/{table_id}/columns",
        json={"title": title, "type": "text"},
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


def test_get_record_rejects_table_from_other_base():
    owning_base = create_base()
    other_base = create_base()
    table = create_table(owning_base["id"])
    field_name = unique("name")
    create_column(owning_base["id"], table["id"], field_name)
    marker = unique("record")
    record = create_record(owning_base["id"], table["id"], {field_name: marker})

    wrong_scope = requests.get(
        f"{API}/bases/{other_base['id']}/tables/{table['id']}/records/{record['id']}",
        headers=h(owner_key(other_base["id"])),
    )
    assert wrong_scope.status_code == 404, wrong_scope.text

    owning_scope = requests.get(
        f"{API}/bases/{owning_base['id']}/tables/{table['id']}/records/{record['id']}",
        headers=h(owner_key(owning_base["id"])),
    )
    assert owning_scope.status_code == 200, owning_scope.text
    assert owning_scope.json()[field_name] == marker
