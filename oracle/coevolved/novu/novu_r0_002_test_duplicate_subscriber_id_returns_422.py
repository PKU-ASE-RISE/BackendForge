import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_duplicate_subscriber_id_returns_422():
    subscriber_id = f"dup-sub-{uuid.uuid4().hex}"

    first_response = requests.post(
        f"{BASE_URL}/v1/subscribers",
        headers=HEADERS,
        json={"subscriberId": subscriber_id, "email": "first@example.com"},
        timeout=30,
    )
    assert first_response.status_code == 201

    second_response = requests.post(
        f"{BASE_URL}/v1/subscribers",
        headers=HEADERS,
        json={"subscriberId": subscriber_id, "email": "second@example.com"},
        timeout=30,
    )
    assert second_response.status_code == 422

    get_response = requests.get(
        f"{BASE_URL}/v1/subscribers/{subscriber_id}",
        headers=HEADERS,
        timeout=30,
    )
    assert get_response.status_code == 200
    assert get_response.json()["email"] == "first@example.com"
