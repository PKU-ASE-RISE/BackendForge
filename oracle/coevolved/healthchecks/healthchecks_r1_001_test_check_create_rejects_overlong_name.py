import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_check_create_rejects_overlong_name():
    api_key = f"bf-probe-overlong-name-{uuid.uuid4().hex}"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    too_long_name = f"{uuid.uuid4().hex}-" + ("x" * 101)

    created = requests.post(
        f"{BASE_URL}/api/v1/checks/",
        json={"name": too_long_name},
        headers=headers,
        timeout=30,
    )
    assert created.status_code == 400, created.text

    listed = requests.get(f"{BASE_URL}/api/v1/checks/", headers=headers, timeout=30)
    assert listed.status_code == 200, listed.text
    assert all(check["name"] != too_long_name for check in listed.json()["checks"])
