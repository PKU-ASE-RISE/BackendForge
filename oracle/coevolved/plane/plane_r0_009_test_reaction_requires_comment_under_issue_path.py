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


def test_reaction_requires_comment_under_issue_path():
    slug = f"probe-reaction-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "Reaction Scope Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text

    project = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Reaction Project", "identifier": "RXP"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    issue_a = api("post", f"/api/workspaces/{slug}/projects/{project_id}/issues", json={"name": "Issue A"})
    issue_b = api("post", f"/api/workspaces/{slug}/projects/{project_id}/issues", json={"name": "Issue B"})
    assert issue_a.status_code == 201, issue_a.text
    assert issue_b.status_code == 201, issue_b.text

    comment_b = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_id}/issues/{issue_b.json()['id']}/comments",
        json={"content": "belongs to issue b"},
    )
    assert comment_b.status_code == 201, comment_b.text

    reaction = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_id}/issues/{issue_a.json()['id']}/comments/{comment_b.json()['id']}/reactions",
        json={"emoji": "+1"},
    )
    assert reaction.status_code in (400, 404), reaction.text
