import os
import uuid
from datetime import datetime

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers(api_key):
    return {"X-Api-Key": api_key, "Content-Type": "application/json"}


def _parse_dt(value):
    assert value is not None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_cron_success_ping_sets_next_ping():
    api_key = f"bf-probe-cron-next-{uuid.uuid4().hex}"
    headers = _headers(api_key)
    schedule = "* * * * *"

    created = requests.post(
        f"{BASE_URL}/api/v1/checks/",
        json={"name": f"cron-next-{uuid.uuid4().hex}", "schedule": schedule, "grace": 120},
        headers=headers,
        timeout=30,
    )
    assert created.status_code == 201, created.text
    check_id = created.json()["id"]
    assert created.json()["kind"] == "cron"
    assert created.json()["schedule"] == schedule

    pinged = requests.post(f"{BASE_URL}/ping/{check_id}", data="ok", timeout=30)
    assert pinged.status_code == 200, pinged.text

    fetched = requests.get(f"{BASE_URL}/api/v1/checks/{check_id}", headers=headers, timeout=30)
    assert fetched.status_code == 200, fetched.text
    check = fetched.json()

    assert check["kind"] == "cron"
    assert check["status"] == "up"
    assert check["last_ping"] is not None
    assert check["next_ping"] is not None
    assert _parse_dt(check["next_ping"]) > _parse_dt(check["last_ping"])
