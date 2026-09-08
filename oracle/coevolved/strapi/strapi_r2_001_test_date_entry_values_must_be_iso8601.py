import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def unique_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def create_content_type(name):
    resp = requests.post(
        f"{BASE_URL}/content-types",
        json={"name": name, "displayName": name.replace("_", " ").title()},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def add_field(content_type_id, name, field_type, **extra):
    payload = {"name": name, "type": field_type}
    payload.update(extra)
    resp = requests.post(
        f"{BASE_URL}/content-types/{content_type_id}/fields",
        json=payload,
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def create_entry(content_type_name, payload):
    resp = requests.post(
        f"{BASE_URL}/content/{content_type_name}", json=payload, headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def get_entry(content_type_name, entry_id):
    resp = requests.get(
        f"{BASE_URL}/content/{content_type_name}/{entry_id}", headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_date_entry_values_must_be_iso8601():
    content_type = unique_name("event")
    ct = create_content_type(content_type)
    add_field(ct["id"], "name", "text")
    add_field(ct["id"], "startsAt", "date")

    invalid_create = requests.post(
        f"{BASE_URL}/content/{content_type}",
        json={"name": "bad", "startsAt": "not-a-date"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert invalid_create.status_code == 400, invalid_create.text

    valid_date = "2026-01-02T03:04:05Z"
    valid = create_entry(content_type, {"name": "good", "startsAt": valid_date})
    invalid_update = requests.put(
        f"{BASE_URL}/content/{content_type}/{valid['id']}",
        json={"startsAt": "still-not-a-date"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert invalid_update.status_code == 400, invalid_update.text

    reloaded = get_entry(content_type, valid["id"])
    assert reloaded["startsAt"] == valid_date
