import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _assert_openapi_error_envelope(resp):
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    assert isinstance(data["error"], str)
    assert "detail" not in data


def test_missing_user_header_uses_openapi_error_schema():
    payload = {"title": f"auth-{uuid.uuid4().hex}", "type": "board"}
    resp = requests.post(f"{BASE_URL}/boards", json=payload, timeout=30)
    _assert_openapi_error_envelope(resp)


def test_empty_user_header_uses_openapi_error_schema():
    payload = {"title": f"auth-empty-{uuid.uuid4().hex}", "type": "board"}
    headers = {"X-User-Id": "", "Content-Type": "application/json"}
    resp = requests.post(f"{BASE_URL}/boards", json=payload, headers=headers, timeout=30)
    _assert_openapi_error_envelope(resp)
