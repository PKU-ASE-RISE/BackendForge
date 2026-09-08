import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def _create_project(headers, title):
    response = requests.post(f"{BASE_URL}/api/v1/projects", headers=headers, json={"title": title}, timeout=30)
    assert response.status_code == 201
    return response.json()


def _create_task(headers, project_id, title):
    response = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/tasks",
        headers=headers,
        json={"title": title},
        timeout=30,
    )
    assert response.status_code == 201
    return response.json()


def test_task_relation_rejects_inaccessible_other_task():
    unique = uuid.uuid4().hex
    user_a_headers = _headers(str(uuid.uuid4()))
    user_b_headers = _headers(str(uuid.uuid4()))

    project_a = _create_project(user_a_headers, f"relation-a-{unique}")
    project_b = _create_project(user_b_headers, f"relation-b-{unique}")
    task_a = _create_task(user_a_headers, project_a["id"], f"source-{unique}")
    task_b = _create_task(user_b_headers, project_b["id"], f"private-target-{unique}")

    relation = requests.post(
        f"{BASE_URL}/api/v1/tasks/{task_a['id']}/relations",
        headers=user_a_headers,
        json={"other_task_id": task_b["id"], "relation_kind": "blocks"},
        timeout=30,
    )
    assert relation.status_code in {400, 403, 404}

    reloaded = requests.get(f"{BASE_URL}/api/v1/tasks/{task_a['id']}", headers=user_a_headers, timeout=30)
    assert reloaded.status_code == 200
    blocks = reloaded.json()["relations"].get("blocks", [])
    assert task_b["id"] not in blocks
