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


def test_collection_list_includes_inherited_child_membership():
    owner_id = str(uuid.uuid4())
    viewer_id = str(uuid.uuid4())
    unique = uuid.uuid4().hex

    assert get("/api/collections", viewer_id).status_code == 200

    parent_resp = post("/api/collections", owner_id, {"name": f"Parent {unique}"})
    assert parent_resp.status_code == 201
    parent = parent_resp.json()

    child_resp = post(
        "/api/collections",
        owner_id,
        {"name": f"Child {unique}", "parentId": parent["id"]},
    )
    assert child_resp.status_code == 201
    child = child_resp.json()

    member_resp = post(
        f"/api/collections/{parent['id']}/members",
        owner_id,
        {"userId": viewer_id, "role": "viewer"},
    )
    assert member_resp.status_code == 201

    direct_child_resp = get(f"/api/collections/{child['id']}", viewer_id)
    assert direct_child_resp.status_code == 200

    list_resp = get("/api/collections", viewer_id)
    assert list_resp.status_code == 200
    collection_ids = {collection["id"] for collection in list_resp.json()["collections"]}
    assert parent["id"] in collection_ids
    assert child["id"] in collection_ids
