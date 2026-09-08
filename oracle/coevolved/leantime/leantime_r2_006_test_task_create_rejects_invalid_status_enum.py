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


def test_task_create_rejects_invalid_status_enum():
    h = headers()
    unique = uuid.uuid4().hex

    project_response = requests.post(
        f"{BASE_URL}/projects",
        json={"name": f"task-status-project-{unique}"},
        headers=h,
        timeout=30,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    task_title = f"invalid-status-task-{unique}"
    response = requests.post(
        f"{BASE_URL}/tasks",
        json={
            "title": task_title,
            "project_id": project_id,
            "status": f"not-a-task-status-{unique}",
        },
        headers=h,
        timeout=30,
    )

    assert 400 <= response.status_code < 500, response.text

    listed = requests.get(f"{BASE_URL}/tasks", params={"project_id": project_id}, headers=h, timeout=30)
    assert listed.status_code == 200
    assert all(task["title"] != task_title for task in listed.json())
