import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30


def _headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Group-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_maintenance_negative_cost_rejected():
    headers = _headers()

    item_response = requests.post(
        f"{BASE_URL}/items",
        json={"name": f"negative-maintenance-host-{uuid.uuid4().hex}"},
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    assert item_response.status_code == 201
    item_id = item_response.json()["id"]

    bad_response = requests.post(
        f"{BASE_URL}/items/{item_id}/maintenance",
        json={"date": "2025-01-15", "description": "invalid refund", "cost": -1.25},
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    assert bad_response.status_code == 400

    list_response = requests.get(
        f"{BASE_URL}/items/{item_id}/maintenance",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    assert list_response.status_code == 200
    assert list_response.json() == []
