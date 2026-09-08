import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 10)
ADMIN_TOKEN = "admin_1"


def h():
    return {"X-API-Key": ADMIN_TOKEN}


def create_content_type():
    name = f"ct_{uuid.uuid4().hex[:10]}"
    resp = requests.post(
        f"{BASE_URL}/content-types",
        json={"name": name, "displayName": "Number Probe"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201
    ct = resp.json()["data"]
    field_resp = requests.post(
        f"{BASE_URL}/content-types/{ct['id']}/fields",
        json={"name": "views", "type": "number"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert field_resp.status_code == 201
    return ct


def test_entry_rejects_non_numeric_number_field():
    ct = create_content_type()

    resp = requests.post(
        f"{BASE_URL}/content/{ct['name']}",
        json={"views": "many"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
