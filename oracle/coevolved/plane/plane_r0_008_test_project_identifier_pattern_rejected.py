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


def test_project_identifier_pattern_rejected():
    slug = f"probe-ident-{uuid.uuid4().hex[:8]}"
    workspace = api("post", "/api/workspaces", json={"name": "Identifier Probe", "slug": slug})
    assert workspace.status_code == 201, workspace.text

    project_name = f"Bad Identifier {uuid.uuid4().hex}"
    created = api(
        "post",
        f"/api/workspaces/{slug}/projects",
        json={"name": project_name, "identifier": "bad1"},
    )
    assert created.status_code in (400, 422), created.text

    listed = api("get", f"/api/workspaces/{slug}/projects")
    assert listed.status_code == 200, listed.text
    assert all(project["name"] != project_name for project in listed.json())
