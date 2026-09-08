import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_download_update_rejects_invalid_status_enum():
    suffix = uuid.uuid4().hex
    download_id = None

    try:
        created = requests.post(
            f"{BASE_URL}/api/downloads",
            json={"url": f"https://example.com/watch?v=invalid-status-{suffix}", "priority": 3},
            headers=HEADERS,
        )
        assert created.status_code == 201
        download_id = created.json()["id"]

        response = requests.put(
            f"{BASE_URL}/api/downloads/{download_id}",
            json={"status": f"paused-{suffix}"},
            headers=HEADERS,
        )

        reloaded = requests.get(f"{BASE_URL}/api/downloads/{download_id}", headers=HEADERS)
        assert reloaded.status_code == 200

        assert response.status_code in (400, 422)
        assert reloaded.json()["status"] == "pending"
    finally:
        if download_id:
            requests.delete(f"{BASE_URL}/api/downloads/{download_id}", headers=HEADERS)
