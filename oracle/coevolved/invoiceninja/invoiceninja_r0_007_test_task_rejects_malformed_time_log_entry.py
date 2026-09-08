import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"task-time-log-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_task_rejects_malformed_time_log_entry():
    response = requests.post(
        f"{BASE_URL}/api/tasks",
        json={
            "description": f"malformed-time-log-{uuid.uuid4().hex}",
            "time_log": [[1700000000]],
            "rate": 125,
        },
        headers=headers(),
        timeout=30,
    )

    assert response.status_code == 422
