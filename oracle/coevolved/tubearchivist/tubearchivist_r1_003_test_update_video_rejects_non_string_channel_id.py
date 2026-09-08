import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-123", "Content-Type": "application/json"}


def test_update_video_rejects_non_string_channel_id():
    title = f"channel-type-update-{uuid.uuid4().hex}"
    video_id = None
    try:
        created = requests.post(
            f"{BASE_URL}/api/videos",
            json={"title": title},
            headers=HEADERS,
        )
        assert created.status_code == 201
        video_id = created.json()["id"]
        original_channel_id = created.json()["channelId"]

        updated = requests.put(
            f"{BASE_URL}/api/videos/{video_id}",
            json={"channelId": 12345},
            headers=HEADERS,
        )
        assert updated.status_code == 400
        assert "error" in updated.json()

        reloaded = requests.get(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
        assert reloaded.status_code == 200
        assert reloaded.json()["channelId"] == original_channel_id
    finally:
        if video_id:
            requests.delete(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
