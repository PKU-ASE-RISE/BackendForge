import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_update_bucket_requires_title():
    unique = uuid.uuid4().hex
    headers = _headers(str(uuid.uuid4()))

    project_response = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=headers,
        json={"title": f"bucket-required-title-project-{unique}"},
        timeout=30,
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    bucket_response = requests.post(
        f"{BASE_URL}/api/v1/projects/{project_id}/buckets",
        headers=headers,
        json={"title": f"bucket-original-{unique}", "limit": 0},
        timeout=30,
    )
    assert bucket_response.status_code == 201
    bucket = bucket_response.json()
    assert bucket["limit"] == 0

    update_response = requests.put(
        f"{BASE_URL}/api/v1/projects/{project_id}/buckets/{bucket['id']}",
        headers=headers,
        json={"limit": 7},
        timeout=30,
    )
    assert update_response.status_code == 400

    reloaded = requests.get(
        f"{BASE_URL}/api/v1/projects/{project_id}/buckets/{bucket['id']}",
        headers=headers,
        timeout=30,
    )
    assert reloaded.status_code == 200
    data = reloaded.json()
    assert data["title"] == f"bucket-original-{unique}"
    assert data["limit"] == 0
