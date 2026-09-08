import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def test_admin_cannot_update_member_roles():
    owner_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())
    viewer_id = str(uuid.uuid4())
    owner_headers = headers(owner_id)
    admin_headers = headers(admin_id)
    suffix = uuid.uuid4().hex

    assert requests.get(f"{BASE_URL}/api/collections", headers=headers(admin_id), timeout=30).status_code == 200
    assert requests.get(f"{BASE_URL}/api/collections", headers=headers(viewer_id), timeout=30).status_code == 200

    collection_resp = requests.post(
        f"{BASE_URL}/api/collections",
        json={"name": f"admin-role-change-{suffix}"},
        headers=owner_headers,
        timeout=30,
    )
    assert collection_resp.status_code == 201
    collection = collection_resp.json()

    admin_member_resp = requests.post(
        f"{BASE_URL}/api/collections/{collection['id']}/members",
        json={"userId": admin_id, "role": "admin"},
        headers=owner_headers,
        timeout=30,
    )
    assert admin_member_resp.status_code == 201

    viewer_member_resp = requests.post(
        f"{BASE_URL}/api/collections/{collection['id']}/members",
        json={"userId": viewer_id, "role": "viewer"},
        headers=owner_headers,
        timeout=30,
    )
    assert viewer_member_resp.status_code == 201
    viewer_member = viewer_member_resp.json()

    update_resp = requests.put(
        f"{BASE_URL}/api/collections/{collection['id']}/members/{viewer_member['id']}",
        json={"role": "admin"},
        headers=admin_headers,
        timeout=30,
    )
    assert update_resp.status_code == 403

    members_resp = requests.get(
        f"{BASE_URL}/api/collections/{collection['id']}/members",
        headers=owner_headers,
        timeout=30,
    )
    assert members_resp.status_code == 200
    viewer_members = [m for m in members_resp.json()["members"] if m["id"] == viewer_member["id"]]
    assert viewer_members and viewer_members[0]["role"] == "viewer"
