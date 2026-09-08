import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_integration_create_requires_credentials_object():
    marker = uuid.uuid4().hex
    provider_id = f"bad-creds-{marker}"

    response = requests.post(
        f"{BASE_URL}/v1/integrations",
        headers=HEADERS,
        json={"channel": "email", "providerId": provider_id, "credentials": None},
        timeout=30,
    )

    assert response.status_code == 422

    list_response = requests.get(
        f"{BASE_URL}/v1/integrations",
        headers=HEADERS,
        params={"page": 0, "limit": 100},
        timeout=30,
    )
    assert list_response.status_code == 200
    assert all(item["providerId"] != provider_id for item in list_response.json()["data"])
