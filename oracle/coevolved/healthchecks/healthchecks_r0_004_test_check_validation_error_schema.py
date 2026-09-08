import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_check_validation_error_schema():
    api_key = f"bf-probe-error-schema-{uuid.uuid4().hex}"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    response = requests.post(
        f"{BASE_URL}/api/v1/checks/",
        json={"name": f"bad-timeout-{uuid.uuid4().hex}", "timeout": 59},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == 400, response.text
    payload = response.json()
    assert "error" in payload, payload
    assert isinstance(payload["error"], str), payload
