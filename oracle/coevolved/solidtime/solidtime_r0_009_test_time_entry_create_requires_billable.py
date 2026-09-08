import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def fresh_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_time_entry_create_requires_billable():
    headers = fresh_headers()
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=headers, timeout=30)
    description = f"missing-billable-entry-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/v1/time-entries",
        headers=headers,
        json={
            "start": "2024-05-03T09:00:00Z",
            "end": "2024-05-03T10:00:00Z",
            "description": description,
        },
        timeout=30,
    )

    assert response.status_code == 422
    entries = requests.get(f"{BASE_URL}/api/v1/time-entries", headers=headers, timeout=30).json()
    assert description not in {entry.get("description") for entry in entries}
