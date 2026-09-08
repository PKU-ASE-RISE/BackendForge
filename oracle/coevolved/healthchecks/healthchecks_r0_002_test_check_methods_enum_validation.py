import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_check_methods_enum_validation():
    api_key = f"bf-probe-methods-enum-{uuid.uuid4().hex}"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    response = requests.post(
        f"{BASE_URL}/api/v1/checks/",
        json={"name": f"bad-methods-{uuid.uuid4().hex}", "methods": "GET"},
        headers=headers,
        timeout=30,
    )

    assert response.status_code == 400, response.text
