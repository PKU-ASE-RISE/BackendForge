import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def create_content_type(display_name):
    name = f"ct_{uuid.uuid4().hex[:10]}"
    resp = requests.post(
        f"{BASE_URL}/content-types",
        json={"name": name, "displayName": display_name},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201
    return resp.json()["data"]


def test_entry_rejects_invalid_relation_reference():
    author_ct = create_content_type("Author Target")
    article_ct = create_content_type("Article Source")

    field_resp = requests.post(
        f"{BASE_URL}/content-types/{article_ct['id']}/fields",
        json={
            "name": "author",
            "type": "relation",
            "target": author_ct["name"],
            "relationType": "oneToOne",
        },
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert field_resp.status_code == 201

    resp = requests.post(
        f"{BASE_URL}/content/{article_ct['name']}",
        json={"author": 999999},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
