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


def create_table(base_id, title):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables",
        json={"title": title},
        headers=h(owner_key(base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_link_column_creates_reciprocal_column():
    base = create_base()
    source = create_table(base["id"], unique("source"))
    target = create_table(base["id"], unique("target"))
    key = owner_key(base["id"])

    link_resp = requests.post(
        f"{API}/bases/{base['id']}/tables/{source['id']}/columns",
        json={
            "title": unique("target_link"),
            "type": "link",
            "options": {"linkedTableId": target["id"]},
        },
        headers=h(key),
    )
    assert link_resp.status_code == 201, link_resp.text

    cols_resp = requests.get(
        f"{API}/bases/{base['id']}/tables/{target['id']}/columns",
        headers=h(key),
    )
    assert cols_resp.status_code == 200, cols_resp.text
    target_columns = cols_resp.json()["items"]

    reciprocal = [
        col
        for col in target_columns
        if col.get("type") == "link"
        and col.get("options", {}).get("linkedTableId") == source["id"]
    ]
    assert reciprocal, target_columns
