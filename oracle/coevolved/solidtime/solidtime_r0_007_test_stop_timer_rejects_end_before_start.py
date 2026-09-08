import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def fresh_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_stop_timer_rejects_end_before_start():
    headers = fresh_headers()
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=headers, timeout=30)
    start_response = requests.post(
        f"{BASE_URL}/api/v1/time-entries/start",
        headers=headers,
        json={
            "start": "2024-05-01T10:00:00Z",
            "billable": False,
            "description": f"timer-stop-validation-{uuid.uuid4().hex}",
        },
        timeout=30,
    )
    assert start_response.status_code == 201
    timer = start_response.json()
    assert timer["end"] is None

    stop_response = requests.put(
        f"{BASE_URL}/api/v1/time-entries/{timer['id']}/stop",
        headers=headers,
        json={"end": "2024-05-01T09:59:59Z"},
        timeout=30,
    )

    assert stop_response.status_code == 422
    reloaded = requests.get(
        f"{BASE_URL}/api/v1/time-entries/{timer['id']}",
        headers=headers,
        timeout=30,
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["end"] is None
