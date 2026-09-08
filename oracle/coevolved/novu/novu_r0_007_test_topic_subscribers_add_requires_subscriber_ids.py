import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_topic_subscribers_add_requires_subscriber_ids():
    marker = uuid.uuid4().hex
    topic_key = f"add-requires-subs-{marker}"
    create_response = requests.post(
        f"{BASE_URL}/v1/topics",
        headers=HEADERS,
        json={"key": topic_key, "name": f"Required add {marker}"},
        timeout=30,
    )
    assert create_response.status_code == 201

    add_response = requests.post(
        f"{BASE_URL}/v1/topics/{topic_key}/subscribers",
        headers=HEADERS,
        json={},
        timeout=30,
    )
    assert add_response.status_code == 422

    list_response = requests.get(
        f"{BASE_URL}/v1/topics/{topic_key}/subscribers",
        headers=HEADERS,
        timeout=30,
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0
    assert list_response.json()["data"] == []
