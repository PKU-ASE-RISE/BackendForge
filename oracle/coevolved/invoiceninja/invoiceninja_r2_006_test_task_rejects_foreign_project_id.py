import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"bf-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def post(path, payload, hdr):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=hdr, timeout=30)


def get(path, hdr, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=hdr, params=params, timeout=30)


def test_task_rejects_foreign_project_id():
    hdr_a = headers()
    hdr_b = headers()

    foreign_project = post("/api/projects", {"name": f"foreign-project-{uuid.uuid4().hex}"}, hdr_b)
    assert foreign_project.status_code == 201, foreign_project.text
    foreign_project_id = foreign_project.json()["id"]

    task = post(
        "/api/tasks",
        {
            "project_id": foreign_project_id,
            "description": "must not link across companies",
            "time_log": [[1700000000, 1700003600]],
            "rate": 100,
        },
        hdr_a,
    )
    assert task.status_code == 422, task.text

    listed = get("/api/tasks", hdr_a, params={"project_id": foreign_project_id})
    assert listed.status_code == 200, listed.text
    assert listed.json()["meta"]["total"] == 0
