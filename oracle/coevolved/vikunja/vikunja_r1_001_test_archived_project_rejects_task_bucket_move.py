import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_archived_project_rejects_task_bucket_move():
    unique = uuid.uuid4().hex
    headers = _headers(str(uuid.uuid4()))

    project_response = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=headers,
        json={"title": f"archived-move-{unique}"},
        timeout=30,
    )
    assert project_response.status_code == 201
    project = project_response.json()

    task_response = requests.post(
        f"{BASE_URL}/api/v1/projects/{project['id']}/tasks",
        headers=headers,
        json={"title": f"task-{unique}"},
        timeout=30,
    )
    assert task_response.status_code == 201
    task = task_response.json()
    assert task["bucket_id"] is None

    bucket_response = requests.post(
        f"{BASE_URL}/api/v1/projects/{project['id']}/buckets",
        headers=headers,
        json={"title": f"bucket-{unique}"},
        timeout=30,
    )
    assert bucket_response.status_code == 201
    bucket = bucket_response.json()

    archive_response = requests.put(
        f"{BASE_URL}/api/v1/projects/{project['id']}",
        headers=headers,
        json={"title": project["title"], "is_archived": True},
        timeout=30,
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["is_archived"] is True

    move_response = requests.put(
        f"{BASE_URL}/api/v1/tasks/{task['id']}/bucket",
        headers=headers,
        json={"bucket_id": bucket["id"]},
        timeout=30,
    )
    assert move_response.status_code == 400

    reloaded = requests.get(f"{BASE_URL}/api/v1/tasks/{task['id']}", headers=headers, timeout=30)
    assert reloaded.status_code == 200
    assert reloaded.json()["bucket_id"] is None
