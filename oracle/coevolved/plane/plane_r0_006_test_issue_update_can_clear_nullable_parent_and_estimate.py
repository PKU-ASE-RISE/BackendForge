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


def test_issue_update_can_clear_nullable_parent_and_estimate():
    slug = f"probe-null-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "Nullable Issue Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text

    project = api("post", f"/api/workspaces/{slug}/projects", json={"name": "Nullable Project", "identifier": "NUL"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    parent = api("post", f"/api/workspaces/{slug}/projects/{project_id}/issues", json={"name": "Parent"})
    assert parent.status_code == 201, parent.text

    child = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project_id}/issues",
        json={"name": "Child", "parentId": parent.json()["id"], "estimate": 8},
    )
    assert child.status_code == 201, child.text
    assert child.json()["parentId"] == parent.json()["id"]
    assert child.json()["estimate"] == 8

    patched = api(
        "patch",
        f"/api/workspaces/{slug}/projects/{project_id}/issues/{child.json()['id']}",
        json={"parentId": None, "estimate": None},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["parentId"] is None
    assert patched.json()["estimate"] is None

    reloaded = api("get", f"/api/workspaces/{slug}/projects/{project_id}/issues/{child.json()['id']}")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["parentId"] is None
    assert reloaded.json()["estimate"] is None
