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
        json={"name": name, "displayName": "Field Type Probe"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )
    assert resp.status_code == 201
    return resp.json()["data"]


def test_invalid_field_type_rejected():
    ct = create_content_type()

    resp = requests.post(
        f"{BASE_URL}/content-types/{ct['id']}/fields",
        json={"name": "mystery", "type": "unsupported_type"},
        headers=h(),
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400

    fields_resp = requests.get(f"{BASE_URL}/content-types/{ct['id']}/fields", headers=h(), timeout=REQUEST_TIMEOUT)
    assert fields_resp.status_code == 200
    assert all(field["name"] != "mystery" for field in fields_resp.json()["data"])
