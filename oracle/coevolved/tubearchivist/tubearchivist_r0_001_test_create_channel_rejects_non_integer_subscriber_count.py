import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_create_channel_rejects_non_integer_subscriber_count():
    payload = {
        "name": f"invalid-subscribers-{uuid.uuid4().hex}",
        "subscriberCount": "many",
    }

    response = requests.post(f"{BASE_URL}/api/channels", json=payload, headers=HEADERS)

    try:
        assert response.status_code == 400
        body = response.json()
        assert "error" in body
    finally:
        try:
            channel_id = response.json().get("id")
        except (AttributeError, ValueError):
            channel_id = None
        if channel_id:
            requests.delete(f"{BASE_URL}/api/channels/{channel_id}", headers=HEADERS)
