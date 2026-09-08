import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(api_key):
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def test_cron_schedule_requires_five_fields():
    api_key = f"bf-probe-five-field-cron-{uuid.uuid4().hex}"
    headers = _headers(api_key)
    check_name = f"six-field-cron-{uuid.uuid4().hex}"

    created = requests.post(
        f"{BASE_URL}/api/v1/checks/",
        json={"name": check_name, "schedule": "*/5 * * * * *", "grace": 120},
        headers=headers,
        timeout=30,
    )
    assert created.status_code == 400, created.text

    listed = requests.get(f"{BASE_URL}/api/v1/checks/", headers=headers, timeout=30)
    assert listed.status_code == 200, listed.text
    assert all(check["name"] != check_name for check in listed.json()["checks"])
