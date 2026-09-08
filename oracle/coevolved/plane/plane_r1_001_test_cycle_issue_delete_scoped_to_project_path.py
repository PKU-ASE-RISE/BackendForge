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


def test_cycle_issue_delete_scoped_to_project_path():
    slug = f"drp-cycle-scope-{uuid.uuid4().hex[:8]}"
    assert api("post", WORKSPACES, json={"name": "DRP Cycle Scope", "slug": slug}).status_code == 201

    project_a = api("post", f"{WORKSPACES}/{slug}/projects", json={"name": "Project A", "identifier": "CYA"})
    project_b = api("post", f"{WORKSPACES}/{slug}/projects", json={"name": "Project B", "identifier": "CYB"})
    assert project_a.status_code == 201, project_a.text
    assert project_b.status_code == 201, project_b.text
    project_a_id = project_a.json()["id"]
    project_b_id = project_b.json()["id"]

    issue = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_a_id}/issues",
        json={"name": f"Cycle scoped issue {uuid.uuid4().hex[:6]}"},
    )
    assert issue.status_code == 201, issue.text
    issue_id = issue.json()["id"]

    cycle = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_a_id}/cycles",
        json={"name": "Scoped Cycle", "startDate": "2027-02-01", "endDate": "2027-02-14"},
    )
    assert cycle.status_code == 201, cycle.text
    cycle_id = cycle.json()["id"]

    add_resp = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_a_id}/cycles/{cycle_id}/issues",
        json={"issueId": issue_id},
    )
    assert add_resp.status_code == 201, add_resp.text

    wrong_delete = api(
        "delete",
        f"{WORKSPACES}/{slug}/projects/{project_b_id}/cycles/{cycle_id}/issues/{issue_id}",
    )
    reloaded = api("get", f"{WORKSPACES}/{slug}/projects/{project_a_id}/cycles/{cycle_id}")

    assert wrong_delete.status_code == 404, wrong_delete.text
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["totalIssues"] == 1
