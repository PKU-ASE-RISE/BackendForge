import os

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_integrations_channel_filter_rejects_invalid_enum():
    response = requests.get(
        f"{BASE_URL}/v1/integrations",
        headers=HEADERS,
        params={"channel": "fax"},
        timeout=30,
    )

    assert response.status_code == 422
