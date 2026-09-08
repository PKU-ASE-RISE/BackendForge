import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def fresh_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def api_get(path, headers, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=30)


def api_post(path, headers, json_data):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=json_data, timeout=30)


def create_project(headers, name, color):
    resp = api_post(
        "/api/v1/projects",
        headers=headers,
        json_data={"name": name, "color": color, "is_billable": True},
    )
    assert resp.status_code == 201
    return resp.json()


def test_time_entry_create_rejects_cross_org_task():
    h_a = fresh_headers()
    h_b = fresh_headers()
    assert api_get("/api/v1/organizations/current", headers=h_a).status_code == 200
    assert api_get("/api/v1/organizations/current", headers=h_b).status_code == 200

    token = uuid.uuid4().hex
    project_a = create_project(h_a, f"project-a-{token}", "#101010")
    task_resp = api_post(
        "/api/v1/tasks",
        headers=h_a,
        json_data={"name": f"task-a-{token}", "project_id": project_a["id"]},
    )
    assert task_resp.status_code == 201
    task_a = task_resp.json()

    project_b = create_project(h_b, f"project-b-{token}", "#202020")
    description = f"cross-org-task-entry-{token}"
    create_resp = api_post(
        "/api/v1/time-entries",
        headers=h_b,
        json_data={
            "start": "2024-05-02T09:00:00Z",
            "end": "2024-05-02T10:00:00Z",
            "project_id": project_b["id"],
            "task_id": task_a["id"],
            "billable": False,
            "description": description,
        },
    )
    assert create_resp.status_code == 422

    list_resp = api_get("/api/v1/time-entries", headers=h_b)
    assert list_resp.status_code == 200
    assert all(entry.get("description") != description for entry in list_resp.json())
