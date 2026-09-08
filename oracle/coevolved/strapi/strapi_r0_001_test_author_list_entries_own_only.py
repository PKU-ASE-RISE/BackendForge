import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"
AUTHOR_TOKEN_1 = "author_3"
AUTHOR_TOKEN_2 = "author_4"


def h(token=ADMIN_TOKEN):
    return {"X-API-Key": token}


def create_content_type():
    name = f"ct_{uuid.uuid4().hex[:10]}"
    resp = requests.post(
        f"{BASE_URL}/content-types",
        json={"name": name, "displayName": "Author Isolation Probe"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201
    ct = resp.json()["data"]
    field_resp = requests.post(
        f"{BASE_URL}/content-types/{ct['id']}/fields",
        json={"name": "title", "type": "text"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert field_resp.status_code == 201
    return ct


def test_author_list_entries_own_only():
    ct = create_content_type()
    first = requests.post(
        f"{BASE_URL}/content/{ct['name']}",
        json={"title": "author one"},
        headers=h(AUTHOR_TOKEN_1),
        timeout=REQUEST_TIMEOUT,
    )
    second = requests.post(
        f"{BASE_URL}/content/{ct['name']}",
        json={"title": "author two"},
        headers=h(AUTHOR_TOKEN_2),
        timeout=REQUEST_TIMEOUT,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]

    resp = requests.get(f"{BASE_URL}/content/{ct['name']}", headers=h(AUTHOR_TOKEN_2), timeout=REQUEST_TIMEOUT)

    assert resp.status_code == 200
    visible_ids = {entry["id"] for entry in resp.json()["data"]}
    assert second_id in visible_ids
    assert first_id not in visible_ids
    assert all(entry["createdBy"] == "4" for entry in resp.json()["data"])
