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


def api_get(path, headers, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=30)


def api_post(path, headers, payload):
    return requests.post(f"{BASE_URL}{path}", headers=headers, json=payload, timeout=30)


def test_time_entry_create_rejects_cross_org_project():
    owner_headers = fresh_headers()
    other_headers = fresh_headers()
    assert api_get("/api/v1/organizations/current", owner_headers).status_code == 200
    assert api_get("/api/v1/organizations/current", other_headers).status_code == 200

    suffix = uuid.uuid4().hex
    project_response = api_post(
        "/api/v1/projects",
        owner_headers,
        {"name": f"foreign-project-{suffix}", "color": "#AA3377", "is_billable": True},
    )
    assert project_response.status_code == 201
    foreign_project_id = project_response.json()["id"]
    marker = f"cross-org-entry-{suffix}"

    response = api_post(
        "/api/v1/time-entries",
        other_headers,
        {
            "start": "2025-02-01T09:00:00Z",
            "end": "2025-02-01T10:00:00Z",
            "project_id": foreign_project_id,
            "billable": False,
            "description": marker,
        },
    )

    current_entries = api_get("/api/v1/time-entries", other_headers).json()
    assert all(entry.get("description") != marker for entry in current_entries)
    assert response.status_code == 422
