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


def test_import_csv_missing_name_rejected():
    h = headers()
    marker = uuid.uuid4().hex

    resp = requests.post(
        f"{BASE_URL}/import/csv",
        headers=h,
        json=[{"description": f"missing-name-{marker}", "serialNumber": f"MISS-{marker}"}],
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
    assert data["items"] == []
