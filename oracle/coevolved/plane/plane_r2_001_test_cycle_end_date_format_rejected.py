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


def test_cycle_end_date_format_rejected():
    slug = f"drp-cycle-date-{uuid.uuid4().hex[:8]}"
    workspace = api("post", WORKSPACES, json={"name": "DRP Cycle Date", "slug": slug})
    assert workspace.status_code == 201, workspace.text
    project = api(
        "post",
        f"{WORKSPACES}/{slug}/projects",
        json={"name": "DRP Cycle Date", "identifier": "DCD"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    cycle_name = f"invalid-cycle-date-{uuid.uuid4().hex}"
    invalid = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/cycles",
        json={"name": cycle_name, "startDate": "2027-02-01", "endDate": "not-a-date"},
    )
    assert invalid.status_code in (400, 422), invalid.text

    listed = api("get", f"{WORKSPACES}/{slug}/projects/{project_id}/cycles")
    assert listed.status_code == 200, listed.text
    assert all(cycle["name"] != cycle_name for cycle in listed.json())
