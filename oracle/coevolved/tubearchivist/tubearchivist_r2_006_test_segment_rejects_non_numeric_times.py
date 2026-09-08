import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_segment_rejects_non_numeric_times():
    suffix = uuid.uuid4().hex
    video_id = None
    segment_id = None
    created_ids = []

    try:
        video = requests.post(
            f"{BASE_URL}/api/videos",
            json={"title": f"segment-time-video-{suffix}"},
            headers=HEADERS,
        )
        assert video.status_code == 201
        video_id = video.json()["id"]

        response = requests.post(
            f"{BASE_URL}/api/videos/{video_id}/segments",
            json={"startTime": "10", "endTime": "20", "category": "sponsor"},
            headers=HEADERS,
        )
        if response.status_code == 201:
            segment_id = response.json()["id"]

        listed = requests.get(f"{BASE_URL}/api/videos/{video_id}/segments", headers=HEADERS)
        assert listed.status_code == 200
        created_ids = [segment["id"] for segment in listed.json()["items"]]

        assert response.status_code in (400, 422)
        assert segment_id is None or segment_id not in created_ids
    finally:
        cleanup_ids = list(dict.fromkeys([*created_ids, segment_id]))
        for cleanup_id in cleanup_ids:
            if cleanup_id:
                requests.delete(f"{BASE_URL}/api/segments/{cleanup_id}", headers=HEADERS)
        if video_id:
            requests.delete(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
