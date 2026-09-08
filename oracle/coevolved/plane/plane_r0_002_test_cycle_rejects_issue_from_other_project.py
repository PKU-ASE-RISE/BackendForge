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


def test_cycle_rejects_issue_from_other_project():
    slug = f"probe-cycle-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "Cycle Scope Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text

    project_a = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Cycle A", "identifier": "CYA"})
    project_b = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Cycle B", "identifier": "CYB"})
    assert project_a.status_code == 201, project_a.text
    assert project_b.status_code == 201, project_b.text
    project_a_id = project_a.json()["id"]
    project_b_id = project_b.json()["id"]

    cycle = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_a_id}/cycles",
        json={"name": "Cycle A Only", "startDate": "2027-01-01", "endDate": "2027-01-15"},
    )
    assert cycle.status_code == 201, cycle.text

    issue = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_b_id}/issues",
        json={"name": f"foreign-cycle-{uuid.uuid4().hex}"},
    )
    assert issue.status_code == 201, issue.text

    added = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_a_id}/cycles/{cycle.json()['id']}/issues",
        json={"issueId": issue.json()["id"]},
    )
    assert added.status_code in (400, 404), added.text

    reloaded = api("get", f"/api/workspaces/{slug}/projects/{project_a_id}/cycles/{cycle.json()['id']}")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["totalIssues"] == 0
