import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
API_KEY = os.environ.get("API_KEY", "test-api-key-123")


def create_site(domain):
    response = requests.post(
        f"{BASE_URL}/api/sites",
        headers={"X-API-Key": API_KEY},
        json={"domain": domain},
    )
    assert response.status_code == 201, response.text


def test_duplicate_site_error_response_uses_error_field():
    domain = f"duplicate-error-{uuid.uuid4().hex}.com"
    create_site(domain)

    response = requests.post(
        f"{BASE_URL}/api/sites",
        headers={"X-API-Key": API_KEY},
        json={"domain": domain},
    )

    assert response.status_code == 400, response.text
    body = response.json()
    assert "error" in body
    assert isinstance(body["error"], str)
