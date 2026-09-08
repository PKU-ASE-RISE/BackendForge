import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_ROOT = "/api"
WORKSPACES = API_ROOT + "/workspaces"
ADMIN_KEY = "admin-key-001"
GUEST_KEY = "guest-key-003"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = key
    kwargs.setdefault("timeout", 30)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers, **kwargs)


def user_id_for_key(api_key):
    slug = f"drp-user-{uuid.uuid4().hex[:8]}"
    created = api("post", WORKSPACES, key=api_key, json={"name": "DRP User Lookup", "slug": slug})
    assert created.status_code == 201, created.text
    members = api("get", f"{WORKSPACES}/{slug}/members", key=api_key)
    assert members.status_code == 200, members.text
    user_id = members.json()[0]["userId"]
    api("delete", f"{WORKSPACES}/{slug}", key=api_key)
    return user_id


def test_guest_cannot_add_comment_reaction():
    slug = f"drp-guest-react-{uuid.uuid4().hex[:8]}"
    assert api("post", WORKSPACES, json={"name": "DRP Guest Reaction", "slug": slug}).status_code == 201

    guest_user_id = user_id_for_key(GUEST_KEY)
    add_guest = api(
        "post",
        f"{WORKSPACES}/{slug}/members",
        json={"userId": guest_user_id, "role": "guest"},
    )
    assert add_guest.status_code == 201, add_guest.text

    project = api("post", f"{WORKSPACES}/{slug}/projects", json={"name": "Reaction Project", "identifier": "RXP"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    issue = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/issues",
        json={"name": f"Reaction issue {uuid.uuid4().hex[:6]}"},
    )
    assert issue.status_code == 201, issue.text
    issue_id = issue.json()["id"]

    comment = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/issues/{issue_id}/comments",
        json={"content": "Admin comment"},
    )
    assert comment.status_code == 201, comment.text
    comment_id = comment.json()["id"]

    reaction = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_id}/issues/{issue_id}/comments/{comment_id}/reactions",
        key=GUEST_KEY,
        json={"emoji": "+1"},
    )
    assert reaction.status_code == 403, reaction.text
