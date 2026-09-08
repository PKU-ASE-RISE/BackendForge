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


def test_module_rejects_issue_from_other_project():
    slug = f"probe-module-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "Module Scope Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text

    project_a = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Module A", "identifier": "MOA"})
    project_b = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Module B", "identifier": "MOB"})
    assert project_a.status_code == 201, project_a.text
    assert project_b.status_code == 201, project_b.text
    project_a_id = project_a.json()["id"]
    project_b_id = project_b.json()["id"]

    module = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_a_id}/modules",
        json={"name": "Module A Only"},
    )
    assert module.status_code == 201, module.text

    issue = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_b_id}/issues",
        json={"name": f"foreign-module-{uuid.uuid4().hex}"},
    )
    assert issue.status_code == 201, issue.text

    added = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_a_id}/modules/{module.json()['id']}/issues",
        json={"issueId": issue.json()["id"]},
    )
    assert added.status_code in (400, 404), added.text

    reloaded = api("get", f"/api/workspaces/{slug}/projects/{project_a_id}/modules/{module.json()['id']}")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["totalIssues"] == 0
