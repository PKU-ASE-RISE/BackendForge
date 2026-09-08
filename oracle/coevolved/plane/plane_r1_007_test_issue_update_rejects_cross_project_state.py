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


def test_issue_update_rejects_cross_project_state():
    slug = f"drp-update-state-{uuid.uuid4().hex[:8]}"
    assert api("post", WORKSPACES, json={"name": "DRP Update State", "slug": slug}).status_code == 201

    project_a = api("post", f"{WORKSPACES}/{slug}/projects", json={"name": "Workflow A", "identifier": "WFA"})
    project_b = api("post", f"{WORKSPACES}/{slug}/projects", json={"name": "Workflow B", "identifier": "WFB"})
    assert project_a.status_code == 201, project_a.text
    assert project_b.status_code == 201, project_b.text
    project_a_id = project_a.json()["id"]
    project_b_id = project_b.json()["id"]

    state_a = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_a_id}/states",
        json={"name": "Todo A", "group": "unstarted", "order": 1},
    )
    state_b = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_b_id}/states",
        json={"name": "Done B", "group": "completed", "order": 1},
    )
    assert state_a.status_code == 201, state_a.text
    assert state_b.status_code == 201, state_b.text
    state_a_id = state_a.json()["id"]
    state_b_id = state_b.json()["id"]

    issue = api(
        "post",
        f"{WORKSPACES}/{slug}/projects/{project_a_id}/issues",
        json={"name": f"Cross state update {uuid.uuid4().hex[:6]}", "stateId": state_a_id},
    )
    assert issue.status_code == 201, issue.text
    issue_id = issue.json()["id"]

    patch = api(
        "patch",
        f"{WORKSPACES}/{slug}/projects/{project_a_id}/issues/{issue_id}",
        json={"stateId": state_b_id},
    )
    reloaded = api("get", f"{WORKSPACES}/{slug}/projects/{project_a_id}/issues/{issue_id}")

    assert patch.status_code in (400, 404), patch.text
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["stateId"] == state_a_id
