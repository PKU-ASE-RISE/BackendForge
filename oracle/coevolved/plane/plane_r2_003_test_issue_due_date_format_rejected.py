import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = "admin-key-001"
API = "/" + "api"
WORKSPACES = API + "/" + "workspaces"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = key
    kwargs.setdefault("timeout", 30)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers, **kwargs)


def test_issue_due_date_format_rejected():
    slug = f"drp-due-date-{uuid.uuid4().hex[:8]}"
    workspace = api("post", WORKSPACES, json={"name": "DRP Due Date", "slug": slug})
    assert workspace.status_code == 201, workspace.text
    project = api(
        "post",
        f"{WORKSPACES}/{slug}/projects",
        json={"name": "DRP Due Date", "identifier": "DDD"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    issue_name = f"invalid-due-date-{uuid.uuid4().hex}"
    invalid = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/issues",
        json={"name": issue_name, "dueDate": "not-a-date"},
    )
    assert invalid.status_code in (400, 422), invalid.text

    listed = api("get", f"{WORKSPACES}/{slug}/projects/{project_id}/issues")
    assert listed.status_code == 200, listed.text
    assert all(issue["name"] != issue_name for issue in listed.json())
