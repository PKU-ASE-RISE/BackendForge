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


def test_import_csv_non_object_row_rejected():
    resp = requests.post(
        f"{BASE_URL}/import/csv",
        headers=headers(),
        json=["not an item object"],
        timeout=REQUEST_TIMEOUT,
    )

    assert resp.status_code == 400
    assert isinstance(resp.json().get("error"), str)
