import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_archived_project_rejects_task_relation_create():
    user_id = str(uuid.uuid4())
    h = headers(user_id)
    unique = uuid.uuid4().hex

    project_resp = requests.post(
        f"{BASE_URL}/api/v1/projects",
        json={"title": f"archive-relation-project-{unique}"},
        headers=h,
        timeout=30,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    first_resp = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/tasks",
        json={"title": f"archive-relation-first-{unique}"},
        headers=h,
        timeout=30,
    )
    second_resp = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/tasks",
        json={"title": f"archive-relation-second-{unique}"},
        headers=h,
        timeout=30,
    )
    assert first_resp.status_code == 201
    assert second_resp.status_code == 201
    first_id = first_resp.json()["id"]
    second_id = second_resp.json()["id"]
    assert first_resp.json()["relations"] == {}
    assert second_resp.json()["relations"] == {}

    archive_resp = requests.put(
        f"{BASE_URL}/api/v1/projects/{project_id}",
        json={"title": f"archive-relation-project-{unique}", "is_archived": True},
        headers=h,
        timeout=30,
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["is_archived"] is True

    relation_resp = requests.post(
        f"{BASE_URL}/api/v1/tasks/{first_id}/relations",
        json={"other_task_id": second_id, "relation_kind": "blocks"},
        headers=h,
        timeout=30,
    )
    assert relation_resp.status_code == 400
    assert "error" in relation_resp.json()

    first_after = requests.get(f"{BASE_URL}/api/v1/tasks/{first_id}", headers=h, timeout=30)
    second_after = requests.get(f"{BASE_URL}/api/v1/tasks/{second_id}", headers=h, timeout=30)
    assert first_after.status_code == 200
    assert second_after.status_code == 200
    assert first_after.json()["relations"] == {}
    assert second_after.json()["relations"] == {}
