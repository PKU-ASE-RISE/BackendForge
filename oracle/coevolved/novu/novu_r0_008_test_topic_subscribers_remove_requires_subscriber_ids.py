import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_topic_subscribers_remove_requires_subscriber_ids():
    marker = uuid.uuid4().hex
    topic_key = f"remove-requires-subs-{marker}"
    subscriber_id = f"remove-member-{marker}"

    assert requests.post(
        f"{BASE_URL}/v1/subscribers",
        headers=HEADERS,
        json={"subscriberId": subscriber_id},
        timeout=30,
    ).status_code == 201
    assert requests.post(
        f"{BASE_URL}/v1/topics",
        headers=HEADERS,
        json={"key": topic_key, "name": f"Required remove {marker}"},
        timeout=30,
    ).status_code == 201
    assert requests.post(
        f"{BASE_URL}/v1/topics/{topic_key}/subscribers",
        headers=HEADERS,
        json={"subscriberIds": [subscriber_id]},
        timeout=30,
    ).status_code == 200

    remove_response = requests.post(
        f"{BASE_URL}/v1/topics/{topic_key}/subscribers/remove",
        headers=HEADERS,
        json={},
        timeout=30,
    )
    assert remove_response.status_code == 422

    list_response = requests.get(
        f"{BASE_URL}/v1/topics/{topic_key}/subscribers",
        headers=HEADERS,
        timeout=30,
    )
    assert list_response.status_code == 200
    assert subscriber_id in list_response.json()["data"]
