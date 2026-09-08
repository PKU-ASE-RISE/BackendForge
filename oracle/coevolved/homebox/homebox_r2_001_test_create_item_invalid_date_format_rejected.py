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


def test_create_item_invalid_date_format_rejected():
    h = headers()
    marker = uuid.uuid4().hex
    item_name = f"BadDateItem-{marker}"

    resp = requests.post(
        f"{BASE_URL}/items",
        headers=h,
        json={
            "name": item_name,
            "serialNumber": f"BADDATE-{marker}",
            "purchaseDate": "not-a-date",
            "warrantyExpires": "2026-99-99",
        },
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
    assert "error" in resp.json()

    reload_resp = requests.get(
        f"{BASE_URL}/items",
        headers=h,
        params={"q": marker, "archived": "all"},
        timeout=REQUEST_TIMEOUT,
    )
    assert reload_resp.status_code == 200
    data = reload_resp.json()
    assert data["total"] == 0
    assert all(item["name"] != item_name for item in data["items"])
