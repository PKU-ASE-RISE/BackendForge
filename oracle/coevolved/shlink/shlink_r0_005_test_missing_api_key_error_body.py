import os

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def test_missing_api_key_error_body():
    response = requests.get(f"{BASE_URL}/rest/v3/domains", timeout=30)

    assert response.status_code == 401, response.text
    payload = response.json()
    assert payload.get("type") == "INVALID_API_KEY"
    assert payload.get("title") == "Invalid API key"
    assert payload.get("status") == 401
    assert (
        payload.get("detail")
        == "Expected one of the following authentication headers, but none were provided"
    )
