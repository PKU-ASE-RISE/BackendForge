import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-Api-Key": f"org-segment-update-match-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_update_segment_rejects_invalid_match_type_enum():
    headers = _headers()
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
        json={"name": f"valid-seg-{uuid.uuid4().hex}", "matchType": "ALL", "rules": []},
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code == 201
    segment = create_resp.json()

    update_resp = requests.put(
        f"{BASE_URL}/api/projects/{project_id}/segments/{segment['id']}",
        json={"name": segment["name"], "matchType": "NONE", "rules": []},
        headers=headers,
        timeout=30,
    )
    assert update_resp.status_code != 200

    reload_resp = requests.get(
        f"{BASE_URL}/api/projects/{project_id}/segments/{segment['id']}",
        headers=headers,
        timeout=30,
    )
    assert reload_resp.status_code == 200
    assert reload_resp.json()["matchType"] == "ALL"
