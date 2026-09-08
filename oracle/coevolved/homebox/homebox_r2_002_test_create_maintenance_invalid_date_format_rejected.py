import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30


def headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Group-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_create_maintenance_invalid_date_format_rejected():
    h = headers()
    marker = uuid.uuid4().hex

    item_resp = requests.post(
        f"{BASE_URL}/items",
        headers=h,
        json={"name": f"MaintenanceDateHost-{marker}"},
        timeout=REQUEST_TIMEOUT,
    )
    assert item_resp.status_code == 201
    item_id = item_resp.json()["id"]

    resp = requests.post(
        f"{BASE_URL}/items/{item_id}/maintenance",
        headers=h,
        json={
            "date": "not-a-date",
            "description": f"bad-date-maintenance-{marker}",
            "cost": 0,
            "scheduledDate": "2026-99-99",
        },
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
    assert "error" in resp.json()

    reload_resp = requests.get(
        f"{BASE_URL}/items/{item_id}/maintenance",
        headers=h,
        timeout=REQUEST_TIMEOUT,
    )
    assert reload_resp.status_code == 200
    assert reload_resp.json() == []
