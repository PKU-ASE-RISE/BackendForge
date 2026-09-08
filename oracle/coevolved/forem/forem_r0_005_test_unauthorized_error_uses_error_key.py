import os

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_unauthorized_error_uses_error_key():
    response = requests.post(
        f"{BASE_URL}/articles",
        json={"title": "No Auth", "body_markdown": "body"},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    assert response.status_code == 401
    body = response.json()
    assert isinstance(body.get("error"), str)
    assert body["error"]
