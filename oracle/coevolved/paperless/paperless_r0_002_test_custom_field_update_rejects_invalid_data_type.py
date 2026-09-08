import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"drp-cf-update-type-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_custom_field_update_rejects_invalid_data_type():
    h = headers()
    name = f"cf-type-{uuid.uuid4().hex}"
    created = requests.post(
        f"{BASE_URL}/api/custom_fields/",
        json={"name": name, "data_type": "string"},
        headers=h,
        timeout=30,
    )
    assert created.status_code == 201, created.text
    field_id = created.json()["id"]

    resp = requests.put(
        f"{BASE_URL}/api/custom_fields/{field_id}/",
        json={"name": name, "data_type": "not_a_valid_type"},
        headers=h,
        timeout=30,
    )

    assert resp.status_code == 400, resp.text

    reloaded = requests.get(f"{BASE_URL}/api/custom_fields/{field_id}/", headers=h, timeout=30)
    assert reloaded.status_code == 200
    assert reloaded.json()["data_type"] == "string"
