import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"task-status-update-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_task_update_rejects_invalid_status():
    hdr = headers()
    create = requests.post(
        f"{BASE_URL}/api/tasks",
        json={
            "description": f"valid-task-{uuid.uuid4().hex}",
            "time_log": [[1700000000, 1700007200]],
            "rate": 90,
            "status": "active",
        },
        headers=hdr,
        timeout=30,
    )
    assert create.status_code == 201
    task_id = create.json()["id"]

    update = requests.put(
        f"{BASE_URL}/api/tasks/{task_id}",
        json={"status": "archived"},
        headers=hdr,
        timeout=30,
    )
    assert update.status_code == 422
    assert "error" in update.json()

    reloaded = requests.get(f"{BASE_URL}/api/tasks/{task_id}", headers=hdr, timeout=30)
    assert reloaded.status_code == 200
    assert reloaded.json()["status"] == "active"
