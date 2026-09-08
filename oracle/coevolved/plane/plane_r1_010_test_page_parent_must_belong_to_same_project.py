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


def test_page_parent_must_belong_to_same_project():
    slug = f"drp-page-parent-{uuid.uuid4().hex[:8]}"
    assert api("post", WORKSPACES, json={"name": "DRP Page Parent", "slug": slug}).status_code == 201

    project_a = api("post", f"{WORKSPACES}/{slug}/projects", json={"name": "Docs A", "identifier": "PGA"})
    project_b = api("post", f"{WORKSPACES}/{slug}/projects", json={"name": "Docs B", "identifier": "PGB"})
    assert project_a.status_code == 201, project_a.text
    assert project_b.status_code == 201, project_b.text
    project_a_id = project_a.json()["id"]
    project_b_id = project_b.json()["id"]

    parent = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_a_id}/pages",
        json={"title": f"Parent {uuid.uuid4().hex[:6]}", "content": "parent"},
    )
    assert parent.status_code == 201, parent.text
    parent_id = parent.json()["id"]

    child_title = f"Cross child {uuid.uuid4().hex[:8]}"
    child = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_b_id}/pages",
        json={"title": child_title, "content": "child", "parentId": parent_id},
    )
    pages_b = api("get", f"{WORKSPACES}/{slug}/projects/{project_b_id}/pages")

    assert child.status_code in (400, 404), child.text
    assert pages_b.status_code == 200, pages_b.text
    assert all(page["title"] != child_title for page in pages_b.json())
