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


def test_issue_assignees_must_be_workspace_members():
    slug = f"drp-assignee-{uuid.uuid4().hex[:8]}"
    assert api("post", WORKSPACES, json={"name": "DRP Assignee", "slug": slug}).status_code == 201

    project = api(
        "post",
        f"{WORKSPACES}/{slug}/projects",
        json={"name": "Assignee Project", "identifier": "ASN"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    fake_member_id = str(uuid.uuid4())
    issue_name = f"Invalid assignee {uuid.uuid4().hex[:8]}"
    issue = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/issues",
        json={"name": issue_name, "assignees": [fake_member_id]},
    )
    issues = api("get", f"{WORKSPACES}/{slug}/projects/{project_id}/issues")

    assert issue.status_code in (400, 404), issue.text
    assert issues.status_code == 200, issues.text
    assert all(fake_member_id not in item.get("assignees", []) for item in issues.json())
