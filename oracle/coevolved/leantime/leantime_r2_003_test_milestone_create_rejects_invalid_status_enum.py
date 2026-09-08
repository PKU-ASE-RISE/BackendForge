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


def test_milestone_create_rejects_invalid_status_enum():
    h = headers()
    unique = uuid.uuid4().hex

    project_response = requests.post(
        f"{BASE_URL}/projects",
        json={"name": f"milestone-status-project-{unique}"},
        headers=h,
        timeout=30,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    milestone_title = f"invalid-status-milestone-{unique}"
    response = requests.post(
        f"{BASE_URL}/milestones",
        json={
            "title": milestone_title,
            "project_id": project_id,
            "status": f"not-a-milestone-status-{unique}",
        },
        headers=h,
        timeout=30,
    )

    assert 400 <= response.status_code < 500, response.text

    listed = requests.get(f"{BASE_URL}/milestones", params={"project_id": project_id}, headers=h, timeout=30)
    assert listed.status_code == 200
    assert all(milestone["title"] != milestone_title for milestone in listed.json())
