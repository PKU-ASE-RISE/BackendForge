import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api_get(path, user_id, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers(user_id), params=params, timeout=30)


def api_post(path, user_id, json_data):
    return requests.post(f"{BASE_URL}{path}", headers=headers(user_id), json=json_data, timeout=30)


def api_delete(path, user_id):
    return requests.delete(f"{BASE_URL}{path}", headers=headers(user_id), timeout=30)


def test_delete_task_group_removes_task_activity():
    suffix = uuid.uuid4().hex
    user_id = str(uuid.uuid4())

    project_response = api_post("/projects", user_id, {"name": f"activity-cascade-{suffix}"})
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    group_response = api_post(f"/projects/{project['id']}/task-groups", user_id, {"name": f"column-{suffix}"})
    assert group_response.status_code == 201, group_response.text
    group = group_response.json()

    task_response = api_post("/tasks", user_id, {"taskGroupId": group["id"], "title": f"task-{suffix}"})
    assert task_response.status_code == 201, task_response.text
    task = task_response.json()

    comment_response = api_post(f"/tasks/{task['id']}/comments", user_id, {"text": f"comment-{suffix}"})
    assert comment_response.status_code == 201, comment_response.text

    delete_response = api_delete(f"/task-groups/{group['id']}", user_id)
    assert delete_response.status_code == 204, delete_response.text

    deleted_task_response = api_get(f"/tasks/{task['id']}", user_id)
    assert deleted_task_response.status_code == 404, deleted_task_response.text

    activity_response = api_get(f"/projects/{project['id']}/activity", user_id, params={"limit": 200})
    assert activity_response.status_code == 200, activity_response.text
    leaked_activity = [entry for entry in activity_response.json() if entry.get("taskId") == task["id"]]
    assert leaked_activity == []
