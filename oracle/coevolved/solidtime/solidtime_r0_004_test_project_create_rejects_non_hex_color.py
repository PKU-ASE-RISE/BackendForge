import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def fresh_headers():
    return {
        "X-User-Id": str(uuid.uuid4()),
        "X-Org-Id": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def test_project_create_rejects_non_hex_color():
    headers = fresh_headers()
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=headers, timeout=30)
    project_name = f"bad-color-create-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=headers,
        json={
            "name": project_name,
            "color": "#GGHHII",
            "is_billable": True,
        },
        timeout=30,
    )

    assert response.status_code == 422
    projects = requests.get(f"{BASE_URL}/api/v1/projects", headers=headers, timeout=30).json()
    assert project_name not in {project["name"] for project in projects}
