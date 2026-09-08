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


def test_goal_create_rejects_invalid_metric_type_enum():
    h = headers()
    unique = uuid.uuid4().hex

    project_response = requests.post(
        f"{BASE_URL}/projects",
        json={"name": f"goal-metric-project-{unique}"},
        headers=h,
        timeout=30,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    goal_title = f"invalid-metric-goal-{unique}"
    response = requests.post(
        f"{BASE_URL}/goals",
        json={
            "title": goal_title,
            "project_id": project_id,
            "metric_type": f"not-a-metric-{unique}",
            "target_value": 10,
            "current_value": 2,
        },
        headers=h,
        timeout=30,
    )

    assert 400 <= response.status_code < 500, response.text

    listed = requests.get(f"{BASE_URL}/goals", params={"project_id": project_id}, headers=h, timeout=30)
    assert listed.status_code == 200
    assert all(goal["title"] != goal_title for goal in listed.json())
