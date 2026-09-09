import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API = f"{BASE_URL}/api/v1"


def unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def h(api_key):
    return {"X-API-Key": api_key}


def key(role, base_id):
    return f"{role}_{base_id}_{uuid.uuid4().hex}"


def create_base():
    # Use delimiter-free key components; underscore parsing is unspecified
    # and unrelated to the behavior under test.
    resp = requests.post(
        f"{API}/bases",
        json={"title": unique("base")},
        headers=h(key("owner", uuid.uuid4().hex)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_table(base_id):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables",
        json={"title": unique("table")},
        headers=h(key("owner", base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_column(base_id, table_id, title):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables/{table_id}/columns",
        json={"title": title, "type": "text"},
        headers=h(key("owner", base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_record(base_id, table_id, payload):
    resp = requests.post(
        f"{API}/bases/{base_id}/tables/{table_id}/records",
        json=payload,
        headers=h(key("owner", base_id)),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_delete_comment_rejects_table_from_other_base():
    owning_base = create_base()
    other_base = create_base()
    table = create_table(owning_base["id"])
    field_name = unique("field")
    create_column(owning_base["id"], table["id"], field_name)
    record = create_record(
        owning_base["id"],
        table["id"],
        {field_name: unique("record")},
    )

    body = unique("comment")
    create_comment = requests.post(
        f"{API}/bases/{owning_base['id']}/tables/{table['id']}/records/{record['id']}/comments",
        json={"body": body},
        headers=h(key("commenter", owning_base["id"])),
    )
    assert create_comment.status_code == 201, create_comment.text
    comment = create_comment.json()

    wrong_scope_delete = requests.delete(
        f"{API}/bases/{other_base['id']}/tables/{table['id']}/records/{record['id']}/comments/{comment['id']}",
        headers=h(key("owner", other_base["id"])),
    )
    assert wrong_scope_delete.status_code in (403, 404), wrong_scope_delete.text

    list_comments = requests.get(
        f"{API}/bases/{owning_base['id']}/tables/{table['id']}/records/{record['id']}/comments",
        headers=h(key("owner", owning_base["id"])),
    )
    assert list_comments.status_code == 200, list_comments.text
    remaining_ids = {item["id"] for item in list_comments.json()["items"]}
    assert comment["id"] in remaining_ids
