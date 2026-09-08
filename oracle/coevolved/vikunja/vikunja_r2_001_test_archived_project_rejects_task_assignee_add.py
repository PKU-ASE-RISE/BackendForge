import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_archived_project_rejects_task_assignee_add():
    owner_id = str(uuid.uuid4())
    assignee_id = str(uuid.uuid4())
    owner_h = headers(owner_id)
    assignee_h = headers(assignee_id)
    unique = uuid.uuid4().hex

    ensure_user = requests.get(f"{BASE_URL}/api/v1/projects", headers=assignee_h, timeout=30)
    assert ensure_user.status_code == 200

    project_resp = requests.post(
        f"{BASE_URL}/api/v1/projects",
        json={"title": f"archive-assignee-project-{unique}"},
        headers=owner_h,
        timeout=30,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    member_resp = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/members",
        json={"user_id": assignee_id, "role": "editor"},
        headers=owner_h,
        timeout=30,
    )
    assert member_resp.status_code == 201

    task_resp = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/tasks",
        json={"title": f"archive-assignee-task-{unique}"},
        headers=owner_h,
        timeout=30,
    )
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]
    assert task_resp.json()["assignees"] == []

    archive_resp = requests.put(
        f"{BASE_URL}/api/v1/projects/{project_id}",
        json={"title": f"archive-assignee-project-{unique}", "is_archived": True},
        headers=owner_h,
        timeout=30,
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["is_archived"] is True

    assign_resp = requests.post(
        f"{BASE_URL}/api/v1/tasks/{task_id}/assignees",
        json={"user_id": assignee_id},
        headers=owner_h,
        timeout=30,
    )
    assert assign_resp.status_code == 400
    assert "error" in assign_resp.json()

    task_after = requests.get(f"{BASE_URL}/api/v1/tasks/{task_id}", headers=owner_h, timeout=30)
    assert task_after.status_code == 200
    data = task_after.json()
    assert data["project_id"] == project_id
    assert data["assignees"] == []
