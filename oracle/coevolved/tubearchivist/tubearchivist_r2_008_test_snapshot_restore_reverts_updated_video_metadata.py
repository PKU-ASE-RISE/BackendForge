import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_snapshot_restore_reverts_updated_video_metadata():
    suffix = uuid.uuid4().hex
    original_title = f"snapshot-original-{suffix}"
    updated_title = f"snapshot-updated-{suffix}"
    video_id = None
    snapshot_id = None

    try:
        created = requests.post(
            f"{BASE_URL}/api/videos",
            json={"title": original_title, "description": "before snapshot", "duration": 11},
            headers=HEADERS,
        )
        assert created.status_code == 201
        video_id = created.json()["id"]

        snapshot = requests.post(
            f"{BASE_URL}/api/snapshots",
            json={"name": f"snap-{suffix}"},
            headers=HEADERS,
        )
        assert snapshot.status_code == 201
        snapshot_id = snapshot.json()["id"]

        updated = requests.put(
            f"{BASE_URL}/api/videos/{video_id}",
            json={"title": updated_title, "description": "after snapshot", "duration": 22},
            headers=HEADERS,
        )
        assert updated.status_code == 200

        restore = requests.post(f"{BASE_URL}/api/snapshots/{snapshot_id}/restore", headers=HEADERS)
        assert restore.status_code == 200

        reloaded = requests.get(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
        assert reloaded.status_code == 200
        body = reloaded.json()
        assert body["title"] == original_title
        assert body["description"] == "before snapshot"
        assert body["duration"] == 11
    finally:
        if video_id:
            requests.delete(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
        if snapshot_id:
            requests.delete(f"{BASE_URL}/api/snapshots/{snapshot_id}", headers=HEADERS)
