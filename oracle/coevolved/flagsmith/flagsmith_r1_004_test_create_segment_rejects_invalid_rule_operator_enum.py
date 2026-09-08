import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-Api-Key": f"org-rule-operator-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_create_segment_rejects_invalid_rule_operator_enum():
    headers = _headers()
    segment_name = f"bad-operator-{uuid.uuid4().hex}"

    project_resp = requests.post(
        f"{BASE_URL}/api/projects",
        json={"name": f"proj-{uuid.uuid4().hex}"},
        headers=headers,
        timeout=30,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    create_resp = requests.post(
        f"{BASE_URL}/api/projects/{project_id}/segments",
        json={
            "name": segment_name,
            "matchType": "ALL",
            "rules": [{"property": "plan", "operator": "STARTS_WITH", "value": "pro"}],
        },
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code != 201

    list_resp = requests.get(
        f"{BASE_URL}/api/projects/{project_id}/segments",
        headers=headers,
        timeout=30,
    )
    assert list_resp.status_code == 200
    assert all(segment["name"] != segment_name for segment in list_resp.json())
