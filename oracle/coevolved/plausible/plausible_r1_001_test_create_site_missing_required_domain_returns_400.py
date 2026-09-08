import os

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")


def test_create_site_missing_required_domain_returns_400():
    response = requests.post(
        f"{BASE_URL}/api/sites",
        headers={"X-API-Key": API_KEY},
        json={"timezone": "UTC"},
    )

    assert response.status_code == 400, response.text
