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


def put(path, user_id, payload):
    return requests.put(f"{BASE_URL}{path}", headers=headers(user_id), json=payload, timeout=30)


def test_collection_update_rejects_cross_user_parent():
    owner_a = str(uuid.uuid4())
    owner_b = str(uuid.uuid4())
    unique = uuid.uuid4().hex

    parent_resp = post("/api/collections", owner_a, {"name": f"foreign-parent-{unique}"})
    assert parent_resp.status_code == 201
    foreign_parent = parent_resp.json()

    private_resp = post("/api/collections", owner_b, {"name": f"private-child-{unique}"})
    assert private_resp.status_code == 201
    private_collection = private_resp.json()
    assert private_collection["parentId"] is None

    update_resp = put(
        f"/api/collections/{private_collection['id']}",
        owner_b,
        {"parentId": foreign_parent["id"]},
    )
    if update_resp.status_code == 200:
        assert update_resp.json()["parentId"] != foreign_parent["id"]
    else:
        assert update_resp.status_code in (400, 403, 404)

    owner_b_reload = get(f"/api/collections/{private_collection['id']}", owner_b)
    assert owner_b_reload.status_code == 200
    assert owner_b_reload.json()["parentId"] != foreign_parent["id"]

    owner_a_probe = get(f"/api/collections/{private_collection['id']}", owner_a)
    assert owner_a_probe.status_code in (403, 404)
