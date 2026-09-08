import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = "admin-key-001"
API = "/" + "api"
WORKSPACES = API + "/" + "workspaces"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = key
    kwargs.setdefault("timeout", 30)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers, **kwargs)


def test_state_update_group_enum_rejected():
    slug = f"drp-state-update-{uuid.uuid4().hex[:8]}"
    workspace = api("post", WORKSPACES, json={"name": "DRP State Update", "slug": slug})
    assert workspace.status_code == 201, workspace.text
    project = api(
        "post",
        f"{WORKSPACES}/{slug}/projects",
        json={"name": "DRP State Update", "identifier": "DSU"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    state = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/states",
        json={"name": "Ready", "group": "unstarted", "order": 1},
    )
    assert state.status_code == 201, state.text
    state_id = state.json()["id"]

    invalid = api(
        "patch",
        f"{WORKSPACES}/{slug}/projects/{project_id}/states/{state_id}",
        json={"group": "archived"},
    )
    assert invalid.status_code in (400, 422), invalid.text

    reloaded = api("get", f"{WORKSPACES}/{slug}/projects/{project_id}/states/{state_id}")
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["group"] == "unstarted"
