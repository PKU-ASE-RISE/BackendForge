import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_KEY = "admin-key-001"
TARGET_KEY = "drp-member-cascade-target-key"
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


def test_removed_workspace_member_removed_from_project_members():
    slug = f"drp-member-cascade-{uuid.uuid4().hex[:8]}"
    workspace = api("post", WORKSPACES, json={"name": "DRP Member Cascade", "slug": slug})
    assert workspace.status_code == 201, workspace.text
    project = api(
        "post",
        f"{WORKSPACES}/{slug}/projects",
        json={"name": "DRP Member Cascade", "identifier": "DMC"},
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    target_user_id = user_id_for(TARGET_KEY)
    workspace_member = api(
        "post",
        f"{WORKSPACES}/{slug}/members",
        json={"userId": target_user_id, "role": "member"},
    )
    assert workspace_member.status_code == 201, workspace_member.text
    workspace_member_id = workspace_member.json()["id"]

    project_member = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/members",
        json={"memberId": workspace_member_id, "role": "member"},
    )
    assert project_member.status_code == 201, project_member.text

    removed = api("delete", f"{WORKSPACES}/{slug}/members/{workspace_member_id}")
    assert removed.status_code == 204, removed.text

    listed = api("get", f"{WORKSPACES}/{slug}/projects/{project_id}/members")
    assert listed.status_code == 200, listed.text
    assert all(member["memberId"] != workspace_member_id for member in listed.json())
