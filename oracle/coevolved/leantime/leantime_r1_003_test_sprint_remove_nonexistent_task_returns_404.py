import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USER_ID = str(uuid.uuid4())
ORG_ID = str(uuid.uuid4())
HEADERS = {"X-User-Id": USER_ID, "X-Org-Id": ORG_ID, "Content-Type": "application/json"}


def post(path, json_data):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def delete(path):
    return requests.delete(f"{BASE_URL}{path}", headers=HEADERS, timeout=30)


def test_sprint_remove_nonexistent_task_returns_404():
    suffix = uuid.uuid4().hex
    project = post("/projects", {"name": f"sprint-project-{suffix}"}).json()
    sprint = post(
        "/sprints",
        {
            "name": f"sprint-{suffix}",
            "project_id": project["id"],
            "start_date": "2026-07-01",
            "end_date": "2026-07-14",
        },
    ).json()

    response = delete(f"/sprints/{sprint['id']}/tasks/{uuid.uuid4()}")

    assert response.status_code == 404, response.text
