import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_update_task_requires_title():
    unique = uuid.uuid4().hex
    headers = _headers(str(uuid.uuid4()))

    project_response = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=headers,
        json={"title": f"task-required-title-project-{unique}"},
        timeout=30,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    task_response = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/tasks",
        headers=headers,
        json={"title": f"original-task-{unique}", "priority": 1},
        timeout=30,
    )
    assert task_response.status_code == 201
    task = task_response.json()
    assert task["priority"] == 1

    update_response = requests.put(
        f"{BASE_URL}/api/v1/tasks/{task['id']}",
        headers=headers,
        json={"priority": 5},
        timeout=30,
    )
    assert update_response.status_code == 400

    reloaded = requests.get(f"{BASE_URL}/api/v1/tasks/{task['id']}", headers=headers, timeout=30)
    assert reloaded.status_code == 200
    data = reloaded.json()
    assert data["title"] == f"original-task-{unique}"
    assert data["priority"] == 1
