import os

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def assert_unauthorized_envelope(response):
    assert response.status_code == 401
    assert response.json() == {"status": "error", "message": "unauthorized"}


def test_missing_and_empty_user_header_return_contract_error_body():
    missing = requests.get(f"{BASE_URL}/api/sports", timeout=30)
    assert_unauthorized_envelope(missing)

    empty = requests.get(f"{BASE_URL}/api/auth/profile", headers={"X-User-Id": ""}, timeout=30)
    assert_unauthorized_envelope(empty)
