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


def test_module_start_date_format_rejected():
    slug = f"drp-module-date-{uuid.uuid4().hex[:8]}"
    workspace = api("post", WORKSPACES, json={"name": "DRP Module Date", "slug": slug})
    assert workspace.status_code == 201, workspace.text
    project = api(
        "post",
        f"{WORKSPACES}/{slug}/projects",
        json={"name": "DRP Module Date", "identifier": "DMD"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    module_name = f"invalid-module-date-{uuid.uuid4().hex}"
    invalid = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/modules",
        json={"name": module_name, "startDate": "not-a-date", "endDate": "2027-04-01"},
    )
    assert invalid.status_code in (400, 422), invalid.text

    listed = api("get", f"{WORKSPACES}/{slug}/projects/{project_id}/modules")
    assert listed.status_code == 200, listed.text
    assert all(module["name"] != module_name for module in listed.json())
