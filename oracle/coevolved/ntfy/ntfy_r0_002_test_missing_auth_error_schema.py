import os

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_missing_auth_error_schema():
    response = requests.get(f"{BASE_URL}/api/topics", timeout=30)

    assert response.status_code == 401
    data = response.json()
    assert data.get("code") == 401
    assert isinstance(data.get("error"), str) and data["error"]
    assert "detail" not in data
