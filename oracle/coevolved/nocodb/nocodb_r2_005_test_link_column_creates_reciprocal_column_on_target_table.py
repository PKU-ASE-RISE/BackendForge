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


def create_table(base_id, title):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables",
        json={"title": title},
        headers=h(owner_key(base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_link_column_creates_reciprocal_column_on_target_table():
    base = create_base()
    source = create_table(base["id"], unique("source"))
    target = create_table(base["id"], unique("target"))

    create_link = requests.post(
        f"{API}/bases/{base['id']}/tables/{source['id']}/columns",
        json={
            "title": unique("target_link"),
            "type": "link",
            "options": {"linkedTableId": target["id"]},
        },
        headers=h(owner_key(base["id"])),
    )
    assert create_link.status_code == 201, create_link.text

    target_columns = requests.get(
        f"{API}/bases/{base['id']}/tables/{target['id']}/columns",
        headers=h(owner_key(base["id"])),
    )
    assert target_columns.status_code == 200, target_columns.text
    reciprocal_links = [
        column
        for column in target_columns.json()["items"]
        if column["type"] == "link"
        and column.get("options", {}).get("linkedTableId") == source["id"]
    ]
    assert reciprocal_links
