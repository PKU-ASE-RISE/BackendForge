import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = "admin-key-001"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    if key:
        headers["X-API-Key"] = key
    kwargs.setdefault("timeout", 30)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers, **kwargs)


def make_workspace_with_projects():
    slug = f"probe-state-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "State Scope Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text
    project_a = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Project A", "identifier": "STA"})
    project_b = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Project B", "identifier": "STB"})
    assert project_a.status_code == 201, project_a.text
    assert project_b.status_code == 201, project_b.text
    return slug, project_a.json(), project_b.json()


def test_issue_rejects_cross_project_state():
    slug, project_a, project_b = make_workspace_with_projects()
    state = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_a['id']}/states",
        json={"name": "Only Project A", "group": "started"},
    )
    assert state.status_code == 201, state.text

    issue_name = f"cross-state-{uuid.uuid4().hex}"
    created = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_b['id']}/issues",
        json={"name": issue_name, "stateId": state.json()["id"]},
    )
    assert created.status_code in (400, 404), created.text

    listed = api("get", f"/api/workspaces/{slug}/projects/{project_b['id']}/issues")
    assert listed.status_code == 200, listed.text
    assert all(issue["name"] != issue_name for issue in listed.json())
