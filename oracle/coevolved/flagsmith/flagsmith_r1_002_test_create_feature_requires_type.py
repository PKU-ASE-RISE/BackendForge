import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-Api-Key": f"org-feature-required-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_create_feature_requires_type():
    headers = _headers()
    project_name = f"proj-{uuid.uuid4().hex}"
    feature_name = f"missing-type-{uuid.uuid4().hex}"

    project_resp = requests.post(
        f"{BASE_URL}/api/projects",
        json={"name": project_name},
        headers=headers,
        timeout=30,
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    create_resp = requests.post(
        f"{BASE_URL}/api/projects/{project_id}/features",
        json={"name": feature_name, "defaultEnabled": True, "initialValue": "created-without-type"},
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code != 201

    list_resp = requests.get(
        f"{BASE_URL}/api/projects/{project_id}/features",
        headers=headers,
        timeout=30,
    )
    assert list_resp.status_code == 200
    assert all(feature["name"] != feature_name for feature in list_resp.json())
