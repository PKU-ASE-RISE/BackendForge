import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def get(path, user_id):
    return requests.get(f"{BASE_URL}{path}", headers=headers(user_id), timeout=30)


def post(path, user_id, payload):
    return requests.post(f"{BASE_URL}{path}", headers=headers(user_id), json=payload, timeout=30)


def delete(path, user_id):
    return requests.delete(f"{BASE_URL}{path}", headers=headers(user_id), timeout=30)


def test_admin_cannot_remove_admin_member():
    owner_id = str(uuid.uuid4())
    admin_a_id = str(uuid.uuid4())
    admin_b_id = str(uuid.uuid4())
    unique = uuid.uuid4().hex

    assert get("/api/collections", admin_a_id).status_code == 200
    assert get("/api/collections", admin_b_id).status_code == 200

    collection_resp = post(
        "/api/collections",
        owner_id,
        {"name": f"Admin remove guard {unique}"},
    )
    assert collection_resp.status_code == 201
    collection = collection_resp.json()

    for admin_id in (admin_a_id, admin_b_id):
        member_resp = post(
            f"/api/collections/{collection['id']}/members",
            owner_id,
            {"userId": admin_id, "role": "admin"},
        )
        assert member_resp.status_code == 201

    members_resp = get(f"/api/collections/{collection['id']}/members", owner_id)
    assert members_resp.status_code == 200
    admin_b_member = next(
        member
        for member in members_resp.json()["members"]
        if member["userId"] == admin_b_id and member["role"] == "admin"
    )

    remove_resp = delete(
        f"/api/collections/{collection['id']}/members/{admin_b_member['id']}",
        admin_a_id,
    )
    assert remove_resp.status_code == 403

    reloaded_resp = get(f"/api/collections/{collection['id']}/members", owner_id)
    assert reloaded_resp.status_code == 200
    assert any(
        member["userId"] == admin_b_id and member["role"] == "admin"
        for member in reloaded_resp.json()["members"]
    )
