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


def test_issue_rejects_cross_project_label():
    slug = f"probe-label-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "Label Scope Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text

    project_a = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Labels A", "identifier": "LAA"})
    project_b = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Labels B", "identifier": "LAB"})
    assert project_a.status_code == 201, project_a.text
    assert project_b.status_code == 201, project_b.text

    label = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_a.json()['id']}/labels",
        json={"name": "Project A Label", "color": "#ff0000"},
    )
    assert label.status_code == 201, label.text

    issue_name = f"cross-label-{uuid.uuid4().hex}"
    created = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_b.json()['id']}/issues",
        json={"name": issue_name, "labels": [label.json()["id"]]},
    )
    assert created.status_code in (400, 404), created.text

    listed = api("get", f"/api/workspaces/{slug}/projects/{project_b.json()['id']}/issues")
    assert listed.status_code == 200, listed.text
    assert all(issue["name"] != issue_name for issue in listed.json())
