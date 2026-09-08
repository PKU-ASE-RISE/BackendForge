import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_archived_project_rejects_task_label_attach():
    user_id = str(uuid.uuid4())
    h = headers(user_id)
    unique = uuid.uuid4().hex

    project_resp = requests.post(
        f"{BASE_URL}/api/v1/projects",
        json={"title": f"archive-label-project-{unique}"},
        headers=h,
        timeout=30,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    task_resp = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/tasks",
        json={"title": f"archive-label-task-{unique}"},
        headers=h,
        timeout=30,
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]
    assert task_resp.json()["labels"] == []

    label_resp = requests.post(
        f"{BASE_URL}/api/v1/labels",
        json={"title": f"archive-label-{unique}", "color": "#12ab34"},
        headers=h,
        timeout=30,
    )
    assert label_resp.status_code == 201
    label_id = label_resp.json()["id"]

    archive_resp = requests.put(
        f"{BASE_URL}/api/v1/projects/{project_id}",
        json={"title": f"archive-label-project-{unique}", "is_archived": True},
        headers=h,
        timeout=30,
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["is_archived"] is True

    attach_resp = requests.post(
        f"{BASE_URL}/api/v1/tasks/{task_id}/labels",
        json={"label_id": label_id},
        headers=h,
        timeout=30,
    )
    assert attach_resp.status_code == 400
    assert "error" in attach_resp.json()

    task_after = requests.get(f"{BASE_URL}/api/v1/tasks/{task_id}", headers=h, timeout=30)
    assert task_after.status_code == 200
    data = task_after.json()
    assert data["project_id"] == project_id
    assert data["labels"] == []
