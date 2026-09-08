import os

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def test_unauthorized_error_schema():
    resp = requests.get(f"{BASE_URL}/accounts", timeout=30)

    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert isinstance(body, dict)
    assert isinstance(body.get("error"), str), body
