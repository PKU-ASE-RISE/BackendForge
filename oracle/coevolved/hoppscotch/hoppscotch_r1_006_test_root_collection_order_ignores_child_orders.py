import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(user):
    return {"X-API-Key": user, "Content-Type": "application/json"}


def test_root_collection_order_ignores_child_orders():
    user = f"order_user_{uuid.uuid4().hex}"

    parent_resp = requests.post(
        f"{BASE_URL}/collections",
        json={"name": f"parent_{uuid.uuid4().hex}"},
        headers=headers(user),
    )
    assert parent_resp.status_code == 201
    parent = parent_resp.json()
    assert parent["parentId"] is None

    child_resp = requests.post(
        f"{BASE_URL}/collections",
        json={
            "name": f"child_{uuid.uuid4().hex}",
            "parentId": parent["id"],
            "order": 77,
        },
        headers=headers(user),
    )
    assert child_resp.status_code == 201
    assert child_resp.json()["parentId"] == parent["id"]

    next_root_resp = requests.post(
        f"{BASE_URL}/collections",
        json={"name": f"next_root_{uuid.uuid4().hex}"},
        headers=headers(user),
    )
    assert next_root_resp.status_code == 201
    next_root = next_root_resp.json()

    reloaded_resp = requests.get(
        f"{BASE_URL}/collections/{next_root['id']}",
        headers=headers(user),
    )
    assert reloaded_resp.status_code == 200
    reloaded = reloaded_resp.json()
    assert reloaded["parentId"] is None
    assert reloaded["order"] == parent["order"] + 1
