import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"task-status-create-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_task_create_rejects_invalid_status():
    hdr = headers()
    response = requests.post(
        f"{BASE_URL}/api/tasks",
        json={
            "description": f"invalid-status-{uuid.uuid4().hex}",
            "time_log": [[1700000000, 1700003600]],
            "rate": 125,
            "status": "archived",
        },
        headers=hdr,
        timeout=30,
    )

    assert response.status_code == 422
    assert "error" in response.json()
