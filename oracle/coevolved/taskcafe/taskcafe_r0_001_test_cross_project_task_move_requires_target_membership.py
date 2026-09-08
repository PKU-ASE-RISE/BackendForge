import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api_get(path, user_id):
    return requests.get(f"{BASE_URL}{path}", headers=headers(user_id), timeout=30)


def api_post(path, user_id, json_data):
    return requests.post(f"{BASE_URL}{path}", headers=headers(user_id), json=json_data, timeout=30)


def api_put(path, user_id, json_data):
    return requests.put(f"{BASE_URL}{path}", headers=headers(user_id), json=json_data, timeout=30)


def create_project(user_id, name):
    response = api_post("/projects", user_id, {"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def create_task_group(user_id, project_id, name):
    response = api_post(f"/projects/{project_id}/task-groups", user_id, {"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def create_task(user_id, task_group_id, title):
    response = api_post("/tasks", user_id, {"taskGroupId": task_group_id, "title": title})
    assert response.status_code == 201, response.text
    return response.json()


def test_cross_project_task_move_requires_target_membership():
    suffix = uuid.uuid4().hex
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())

    project_a = create_project(user_a, f"move-source-{suffix}")
    group_a = create_task_group(user_a, project_a["id"], f"source-column-{suffix}")
    task = create_task(user_a, group_a["id"], f"source-task-{suffix}")

    project_b = create_project(user_b, f"move-target-{suffix}")
    group_b = create_task_group(user_b, project_b["id"], f"target-column-{suffix}")

    response = api_put(
        f"/tasks/{task['id']}",
        user_a,
        {"taskGroupId": group_b["id"], "position": 12345.0},
    )

    assert response.status_code == 403, response.text

    reloaded = api_get(f"/tasks/{task['id']}", user_a)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["taskGroupId"] == group_a["id"]
