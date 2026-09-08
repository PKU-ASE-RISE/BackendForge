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


def test_view_requires_filters_object():
    slug = f"probe-view-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "View Required Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text

    project = api("post", f"/api/workspaces/{slug}/projects", json={"name": "View Project", "identifier": "VRP"})
    assert project.status_code == 201, project.text

    view_name = f"missing-filters-{uuid.uuid4().hex}"
    created = api(
        "post",
        f"/api/workspaces/{slug}/projects/{project.json()['id']}/views",
        json={"name": view_name},
    )
    assert created.status_code in (400, 422), created.text

    listed = api("get", f"/api/workspaces/{slug}/projects/{project.json()['id']}/views")
    assert listed.status_code == 200, listed.text
    assert all(view["name"] != view_name for view in listed.json())
