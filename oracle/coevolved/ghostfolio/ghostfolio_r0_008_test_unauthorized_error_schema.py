import os

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def test_unauthorized_error_schema():
    response = requests.get(f"{BASE_URL}/api/user", timeout=30)

    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert isinstance(data["error"], str)
    assert data["error"]
