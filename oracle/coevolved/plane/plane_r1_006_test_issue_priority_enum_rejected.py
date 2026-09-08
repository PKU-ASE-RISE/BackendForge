import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_ROOT = "/api"
WORKSPACES = API_ROOT + "/workspaces"
ADMIN_KEY = "admin-key-001"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = key
    kwargs.setdefault("timeout", 30)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers, **kwargs)


def test_issue_priority_enum_rejected():
    slug = f"drp-priority-enum-{uuid.uuid4().hex[:8]}"
    assert api("post", WORKSPACES, json={"name": "DRP Priority Enum", "slug": slug}).status_code == 201

    project = api(
        "post",
        f"{WORKSPACES}/{slug}/projects",
        json={"name": "Priority Enum Project", "identifier": "PRI"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    response = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/issues",
        json={"name": f"Invalid priority {uuid.uuid4().hex[:6]}", "priority": "blocker"},
    )
    assert response.status_code in (400, 422), response.text
