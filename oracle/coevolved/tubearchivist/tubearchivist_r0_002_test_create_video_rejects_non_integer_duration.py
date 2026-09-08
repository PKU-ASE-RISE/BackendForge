import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = "test-api-key-123"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def test_create_video_rejects_non_integer_duration():
    payload = {
        "title": f"invalid-duration-{uuid.uuid4().hex}",
        "duration": "3600",
    }

    response = requests.post(f"{BASE_URL}/api/videos", json=payload, headers=HEADERS)

    try:
        assert response.status_code == 400
        body = response.json()
        assert "error" in body
    finally:
        try:
            video_id = response.json().get("id")
        except (AttributeError, ValueError):
            video_id = None
        if video_id:
            requests.delete(f"{BASE_URL}/api/videos/{video_id}", headers=HEADERS)
