import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
USER_ID = str(uuid.uuid4())
ORG_ID = str(uuid.uuid4())
ASSIGNEE_ID = str(uuid.uuid4())
HEADERS = {"X-User-Id": USER_ID, "X-Org-Id": ORG_ID, "Content-Type": "application/json"}


def get(path, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=HEADERS, timeout=30)


def post(path, json_data):
    return requests.post(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def put(path, json_data):
    return requests.put(f"{BASE_URL}{path}", json=json_data, headers=HEADERS, timeout=30)


def test_task_update_nullable_fields_clear():
    suffix = uuid.uuid4().hex
    project = post("/projects", {"name": f"nullable-project-{suffix}"}).json()
    milestone = post(
        "/milestones",
        {"title": f"nullable-milestone-{suffix}", "project_id": project["id"]},
    ).json()
    task = post(
        "/tasks",
        {
            "title": f"nullable-task-{suffix}",
            "project_id": project["id"],
            "milestone_id": milestone["id"],
            "assigned_to": ASSIGNEE_ID,
            "due_date": "2026-06-15",
        },
    ).json()

    response = put(
        f"/tasks/{task['id']}",
        {"milestone_id": None, "assigned_to": None, "due_date": None},
    )

    assert response.status_code == 200, response.text
    reloaded = get(f"/tasks/{task['id']}").json()
    assert reloaded["milestone_id"] is None
    assert reloaded["assigned_to"] is None
    assert reloaded["due_date"] is None
