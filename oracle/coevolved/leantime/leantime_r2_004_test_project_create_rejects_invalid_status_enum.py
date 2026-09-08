import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_project_create_rejects_invalid_status_enum():
    h = headers()
    unique = uuid.uuid4().hex
    project_name = f"invalid-status-project-{unique}"

    response = requests.post(
        f"{BASE_URL}/projects",
        json={"name": project_name, "status": f"not-a-project-status-{unique}"},
        headers=h,
        timeout=30,
    )

    assert 400 <= response.status_code < 500, response.text

    listed = requests.get(f"{BASE_URL}/projects", headers=h, timeout=30)
    assert listed.status_code == 200
    assert all(project["name"] != project_name for project in listed.json())
