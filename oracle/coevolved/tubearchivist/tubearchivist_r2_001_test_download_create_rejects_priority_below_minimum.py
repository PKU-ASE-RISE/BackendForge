import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_download_create_rejects_priority_below_minimum():
    suffix = uuid.uuid4().hex
    download_url = f"https://example.com/watch?v=priority-{suffix}"
    download_id = None

    try:
        response = requests.post(
            f"{BASE_URL}/api/downloads",
            json={"url": download_url, "priority": 0},
            headers=HEADERS,
        )
        if response.status_code == 201:
            download_id = response.json()["id"]

        listed = requests.get(f"{BASE_URL}/api/downloads", params={"limit": 100}, headers=HEADERS)
        assert listed.status_code == 200
        matching = [item for item in listed.json()["items"] if item["url"] == download_url]
        if matching and download_id is None:
            download_id = matching[0].get("id")

        assert response.status_code in (400, 422)
        assert matching == []
    finally:
        if download_id:
            requests.delete(f"{BASE_URL}/api/downloads/{download_id}", headers=HEADERS)
