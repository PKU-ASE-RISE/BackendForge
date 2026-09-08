import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_update_channel_rejects_non_boolean_subscribed():
    channel_id = None
    try:
        create = requests.post(
            f"{BASE_URL}/api/channels",
            json={"name": f"subscribed-type-{uuid.uuid4().hex}"},
            headers=HEADERS,
        )
        assert create.status_code == 201
        channel_id = create.json()["id"]

        response = requests.put(
            f"{BASE_URL}/api/channels/{channel_id}",
            json={"subscribed": "false"},
            headers=HEADERS,
        )

        assert response.status_code == 400
        body = response.json()
        assert "error" in body

        reloaded = requests.get(f"{BASE_URL}/api/channels/{channel_id}", headers=HEADERS)
        assert reloaded.status_code == 200
        assert reloaded.json()["subscribed"] is True
    finally:
        if channel_id:
            requests.delete(f"{BASE_URL}/api/channels/{channel_id}", headers=HEADERS)
