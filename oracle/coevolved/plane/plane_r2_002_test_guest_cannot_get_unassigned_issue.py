import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = "admin-key-001"
GUEST_KEY = "guest-key-003"
API = "/" + "api"
WORKSPACES = API + "/" + "workspaces"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = key
    kwargs.setdefault("timeout", 30)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers, **kwargs)


def user_id_for(api_key):
    slug = f"drp-uid-{uuid.uuid4().hex[:8]}"
    created = api("post", WORKSPACES, key=api_key, json={"name": "DRP UID", "slug": slug})
    assert created.status_code == 201, created.text
    members = api("get", f"{WORKSPACES}/{slug}/members", key=api_key)
    assert members.status_code == 200, members.text
    user_id = members.json()[0]["userId"]
    api("delete", f"{WORKSPACES}/{slug}", key=api_key)
    return user_id


def test_guest_cannot_get_unassigned_issue():
    slug = f"drp-guest-detail-{uuid.uuid4().hex[:8]}"
    workspace = api("post", WORKSPACES, json={"name": "DRP Guest Detail", "slug": slug})
    assert workspace.status_code == 201, workspace.text
    guest_user_id = user_id_for(GUEST_KEY)
    guest_member = api(
        "post",
        f"{WORKSPACES}/{slug}/members",
        json={"userId": guest_user_id, "role": "guest"},
    )
    assert guest_member.status_code == 201, guest_member.text

    project = api(
        "post",
        f"{WORKSPACES}/{slug}/projects",
        json={"name": "DRP Guest Detail", "identifier": "DGD"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    issue = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/issues",
        json={"name": f"unassigned-{uuid.uuid4().hex}"},
    )
    assert issue.status_code == 201, issue.text

    response = api("get", f"{WORKSPACES}/{slug}/projects/{project_id}/issues/{issue.json()['id']}", key=GUEST_KEY)
    assert response.status_code in (403, 404), response.text
