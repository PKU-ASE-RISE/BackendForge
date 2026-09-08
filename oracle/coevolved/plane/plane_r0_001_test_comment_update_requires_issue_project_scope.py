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


def test_comment_update_requires_issue_project_scope():
    slug = f"probe-comment-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "Comment Scope Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text

    project_a = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Comment A", "identifier": "COA"})
    project_b = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Comment B", "identifier": "COB"})
    assert project_a.status_code == 201, project_a.text
    assert project_b.status_code == 201, project_b.text

    issue_b = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_b.json()['id']}/issues",
        json={"name": f"comment-owner-{uuid.uuid4().hex}"},
    )
    assert issue_b.status_code == 201, issue_b.text

    original_content = f"original-{uuid.uuid4().hex}"
    comment = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_b.json()['id']}/issues/{issue_b.json()['id']}/comments",
        json={"content": original_content},
    )
    assert comment.status_code == 201, comment.text

    updated = api(
        "patch",
        f"/api/workspaces/{slug}/projects/{project_a.json()['id']}/issues/{issue_b.json()['id']}/comments/{comment.json()['id']}",
        json={"content": f"wrong-project-{uuid.uuid4().hex}"},
    )
    assert updated.status_code == 404, updated.text

    comments = api(
        "get",
        f"/api/workspaces/{slug}/projects/{project_b.json()['id']}/issues/{issue_b.json()['id']}/comments",
    )
    assert comments.status_code == 200, comments.text
    stored = [item for item in comments.json() if item["id"] == comment.json()["id"]]
    assert stored and stored[0]["content"] == original_content
