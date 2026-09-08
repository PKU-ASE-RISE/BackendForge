import os

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
REQUEST_TIMEOUT = 30


def test_missing_auth_error_response_matches_error_schema():
    response = requests.get(f"{BASE_URL}/items", timeout=REQUEST_TIMEOUT)

    assert response.status_code == 401
    payload = response.json()
    assert isinstance(payload, dict)
    assert "error" in payload
    assert isinstance(payload["error"], str)
    assert payload["error"]
