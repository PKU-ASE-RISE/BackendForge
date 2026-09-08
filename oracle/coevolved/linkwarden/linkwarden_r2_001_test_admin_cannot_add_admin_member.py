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


def test_admin_cannot_add_admin_member():
    owner_id = str(uuid.uuid4())
    admin_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    unique = uuid.uuid4().hex

    assert get("/api/collections", admin_id).status_code == 200
    assert get("/api/collections", target_id).status_code == 200

    collection_resp = post("/api/collections", owner_id, {"name": f"admin-add-guard-{unique}"})
    assert collection_resp.status_code == 201
    collection = collection_resp.json()

    admin_member_resp = post(
        f"/api/collections/{collection['id']}/members",
        owner_id,
        {"userId": admin_id, "role": "admin"},
    )
    assert admin_member_resp.status_code == 201

    add_admin_resp = post(
        f"/api/collections/{collection['id']}/members",
        admin_id,
        {"userId": target_id, "role": "admin"},
    )
    assert add_admin_resp.status_code == 403

    members_resp = get(f"/api/collections/{collection['id']}/members", owner_id)
    assert members_resp.status_code == 200
    assert not any(
        member["userId"] == target_id and member["role"] == "admin"
        for member in members_resp.json()["members"]
    )
