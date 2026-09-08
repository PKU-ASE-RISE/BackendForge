import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-123", "Content-Type": "application/json"}


def test_update_video_rejects_tags_with_non_string_item():
    title = f"tag-item-update-{uuid.uuid4().hex}"
    original_tags = ["one", "two"]
    video_id = None
    try:
        created = requests.post(
            f"{BASE_URL}/api/videos",
            json={"title": title, "tags": original_tags},
            headers=HEADERS,
        )
        assert created.status_code == 201
        video_id = created.json()["id"]

        updated = requests.put(
            f"{BASE_URL}/api/videos/{video_id}",
            json={"tags": ["one", 2]},
            headers=HEADERS,
        )
        assert updated.status_code == 400
        assert "error" in updated.json()

        reloaded = requests.get(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
        assert reloaded.status_code == 200
        assert reloaded.json()["tags"] == original_tags
    finally:
        if video_id:
            requests.delete(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
