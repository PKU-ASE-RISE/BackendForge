import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 10


def request(method, url, **kwargs):
    timeout = kwargs.pop("timeout", REQUEST_TIMEOUT)
    return requests.request(method, url, timeout=timeout, **kwargs)


def headers(api_key):
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _find_member(members, member_id):
    for member in members:
        if member.get("id") == member_id:
            return member
    return None


def test_member_records_are_workspace_scoped():
    marker = uuid.uuid4().hex
    owner_a = f"owner_member_scope_a_{marker}"
    owner_b = f"owner_member_scope_b_{marker}"
    email = f"scoped-member-{marker}@example.test"

    created = request(
        "post",
        f"{BASE_URL}/members",
        headers=headers(owner_a),
        json={"email": email, "name": f"Scoped Member {marker[:8]}", "role": "member"},
    )
    assert created.status_code == 201, created.text
    member = created.json()
    member_id = member["id"]
    assert member["role"] == "member"

    same_workspace_list = request("get", f"{BASE_URL}/members", headers=headers(owner_a))
    assert same_workspace_list.status_code == 200, same_workspace_list.text
    same_workspace_member = _find_member(same_workspace_list.json().get("data", []), member_id)
    assert same_workspace_member is not None
    assert same_workspace_member["email"] == email

    other_workspace_patch = request(
        "patch",
        f"{BASE_URL}/members/{member_id}",
        headers=headers(owner_b),
        json={"role": "admin"},
    )
    assert other_workspace_patch.status_code == 404, other_workspace_patch.text

    reloaded_owner_a = request("get", f"{BASE_URL}/members", headers=headers(owner_a))
    assert reloaded_owner_a.status_code == 200, reloaded_owner_a.text
    reloaded_member = _find_member(reloaded_owner_a.json().get("data", []), member_id)
    assert reloaded_member is not None
    assert reloaded_member["role"] == "member"

    other_workspace_list = request("get", f"{BASE_URL}/members", headers=headers(owner_b))
    assert other_workspace_list.status_code == 200, other_workspace_list.text
    leaked_members = other_workspace_list.json().get("data", [])
    assert member_id not in {item.get("id") for item in leaked_members}
    assert email not in {item.get("email") for item in leaked_members}
