import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers_for():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def api_get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def api_post(path, json_data, headers):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=headers, timeout=30)


def test_equipment_create_rejects_label_longer_than_openapi_limit():
    headers = headers_for()
    long_label = "x" * 51

    resp = api_post(
        "/api/equipments",
        {"label": long_label, "equipment_type_id": 1, "description": "too long label"},
        headers=headers,
    )

    assert resp.status_code == 400
    listed = api_get("/api/equipments", headers=headers)
    assert listed.status_code == 200
    assert all(equipment["label"] != long_label for equipment in listed.json()["data"]["equipments"])
