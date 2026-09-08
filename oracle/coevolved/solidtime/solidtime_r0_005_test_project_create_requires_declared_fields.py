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


def test_project_create_requires_declared_fields():
    headers = fresh_headers()
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=headers, timeout=30)
    missing_color_name = f"missing-color-{uuid.uuid4().hex}"
    missing_billable_name = f"missing-billable-{uuid.uuid4().hex}"

    missing_color = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=headers,
        json={
            "name": missing_color_name,
            "is_billable": True,
        },
        timeout=30,
    )
    missing_billable = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=headers,
        json={
            "name": missing_billable_name,
            "color": "#123456",
        },
        timeout=30,
    )

    assert missing_color.status_code == 422
    assert missing_billable.status_code == 422
    projects = requests.get(f"{BASE_URL}/api/v1/projects", headers=headers, timeout=30).json()
    project_names = {project["name"] for project in projects}
    assert missing_color_name not in project_names
    assert missing_billable_name not in project_names
