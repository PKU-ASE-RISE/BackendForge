import os

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def test_unauthorized_error_body_matches_schema():
    response = requests.get(f"{BASE_URL}/accounts", timeout=30)

    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert isinstance(body["error"], str)
    assert "detail" not in body
