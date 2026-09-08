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


def test_goal_update_rejects_self_parent_cycle():
    h = headers()
    unique = uuid.uuid4().hex

    project_response = requests.post(
        f"{BASE_URL}/projects",
        json={"name": f"self-parent-project-{unique}"},
        headers=h,
        timeout=30,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    goal_response = requests.post(
        f"{BASE_URL}/goals",
        json={
            "title": f"self-parent-goal-{unique}",
            "project_id": project_id,
            "metric_type": "number",
            "target_value": 100,
            "current_value": 25,
        },
        headers=h,
        timeout=30,
    )
    assert goal_response.status_code == 201
    goal = goal_response.json()

    update_response = requests.put(
        f"{BASE_URL}/goals/{goal['id']}",
        json={"parent_goal_id": goal["id"]},
        headers=h,
        timeout=30,
    )

    assert 400 <= update_response.status_code < 500, update_response.text

    after = requests.get(f"{BASE_URL}/goals/{goal['id']}", headers=h, timeout=30)
    assert after.status_code == 200
    assert after.json()["parent_goal_id"] is None
