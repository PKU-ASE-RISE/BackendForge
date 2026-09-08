import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def _headers():
    return {"X-Api-Key": f"project-body-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_create_project_rejects_non_object_body():
    headers = _headers()

    create_resp = requests.post(
        f"{BASE_URL}/api/v1/projects",
        json=[{"name": f"not-an-object-{uuid.uuid4().hex}"}],
        headers=headers,
        timeout=30,
    )
    list_resp = requests.get(f"{BASE_URL}/api/v1/projects", headers=headers, timeout=30)

    assert list_resp.status_code == 200, list_resp.text
    assert create_resp.status_code == 400, create_resp.text
    assert list_resp.json()["data"] == []
