import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_duplicate_topic_key_returns_422():
    topic_key = f"dup-topic-{uuid.uuid4().hex}"

    first_response = requests.post(
        f"{BASE_URL}/v1/topics",
        headers=HEADERS,
        json={"key": topic_key, "name": "Original topic"},
        timeout=30,
    )
    assert first_response.status_code == 201

    second_response = requests.post(
        f"{BASE_URL}/v1/topics",
        headers=HEADERS,
        json={"key": topic_key, "name": "Duplicate topic"},
        timeout=30,
    )
    assert second_response.status_code == 422

    get_response = requests.get(
        f"{BASE_URL}/v1/topics/{topic_key}",
        headers=HEADERS,
        timeout=30,
    )
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Original topic"
