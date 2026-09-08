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


def test_project_update_rejects_non_hex_color():
    headers = fresh_headers()
    requests.get(f"{BASE_URL}/api/v1/organizations/current", headers=headers, timeout=30)
    create_response = requests.post(
        f"{BASE_URL}/api/v1/projects",
        headers=headers,
        json={
            "name": f"bad-color-update-{uuid.uuid4().hex}",
            "color": "#12ABEF",
            "is_billable": True,
        },
        timeout=30,
    )
    assert create_response.status_code == 201
    project = create_response.json()

    update_response = requests.put(
        f"{BASE_URL}/api/v1/projects/{project['id']}",
        headers=headers,
        json={"color": "#12ZZ89"},
        timeout=30,
    )

    assert update_response.status_code == 422
    reloaded = requests.get(
        f"{BASE_URL}/api/v1/projects/{project['id']}",
        headers=headers,
        timeout=30,
    )
    assert reloaded.status_code == 200
    assert reloaded.json()["color"] == "#12ABEF"
