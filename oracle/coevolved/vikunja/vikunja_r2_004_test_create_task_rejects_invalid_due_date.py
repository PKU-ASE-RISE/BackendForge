import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_create_task_rejects_invalid_due_date():
    user_id = str(uuid.uuid4())
    h = headers(user_id)
    unique = uuid.uuid4().hex
    task_title = f"invalid-due-date-task-{unique}"

    project_resp = requests.post(
        f"{BASE_URL}/api/v1/projects",
        json={"title": f"invalid-due-date-project-{unique}"},
        headers=h,
        timeout=30,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    create_resp = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/tasks",
        json={"title": task_title, "due_date": "not-a-date"},
        headers=h,
        timeout=30,
    )
    assert create_resp.status_code == 400
    assert "error" in create_resp.json()

    tasks_resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}/tasks", headers=h, timeout=30)
    assert tasks_resp.status_code == 200
    tasks = tasks_resp.json()
    assert all(task["title"] != task_title for task in tasks)
