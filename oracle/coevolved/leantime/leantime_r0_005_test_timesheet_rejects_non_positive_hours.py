import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def post(path, payload, h):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=h, timeout=30)


def get(path, h):
    return requests.get(f"{BASE_URL}{path}", headers=h, timeout=30)


def test_timesheet_rejects_non_positive_hours():
    h = headers()
    marker = f"bad-hours-{uuid.uuid4().hex}"

    project = post("/projects", {"name": f"Project-{marker}"}, h).json()
    task = post("/tasks", {"title": f"Task-{marker}", "project_id": project["id"]}, h).json()

    for invalid_hours in (0, -1.5):
        response = post(
            "/timesheets",
            {
                "task_id": task["id"],
                "hours": invalid_hours,
                "date": "2026-05-23",
                "description": f"invalid {invalid_hours}",
            },
            h,
        )
        assert response.status_code in {400, 422}

    task_after_attempts = get(f"/tasks/{task['id']}", h)
    assert task_after_attempts.status_code == 200
    assert task_after_attempts.json()["spent_hours"] == 0
