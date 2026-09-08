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


def test_sprint_create_rejects_invalid_date_format():
    h = headers()
    unique = uuid.uuid4().hex

    project_response = requests.post(
        f"{BASE_URL}/projects",
        json={"name": f"sprint-date-project-{unique}"},
        headers=h,
        timeout=30,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    sprint_name = f"invalid-date-sprint-{unique}"
    response = requests.post(
        f"{BASE_URL}/sprints",
        json={
            "name": sprint_name,
            "project_id": project_id,
            "start_date": "not-a-date",
            "end_date": "also-not-a-date",
        },
        headers=h,
        timeout=30,
    )

    assert 400 <= response.status_code < 500, response.text

    listed = requests.get(f"{BASE_URL}/sprints", params={"project_id": project_id}, headers=h, timeout=30)
    assert listed.status_code == 200
    assert all(sprint["name"] != sprint_name for sprint in listed.json())
