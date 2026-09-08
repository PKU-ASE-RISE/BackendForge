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


def delete(path, user_id, params=None):
    return requests.delete(f"{BASE_URL}{path}", headers=headers(user_id), params=params, timeout=30)


def test_cascade_delete_removes_descendant_links():
    owner_id = str(uuid.uuid4())
    unique = uuid.uuid4().hex

    parent_resp = post("/api/collections", owner_id, {"name": f"Cascade parent {unique}"})
    assert parent_resp.status_code == 201
    parent = parent_resp.json()

    child_resp = post(
        "/api/collections",
        owner_id,
        {"name": f"Cascade child {unique}", "parentId": parent["id"]},
    )
    assert child_resp.status_code == 201
    child = child_resp.json()

    grandchild_resp = post(
        "/api/collections",
        owner_id,
        {"name": f"Cascade grandchild {unique}", "parentId": child["id"]},
    )
    assert grandchild_resp.status_code == 201
    grandchild = grandchild_resp.json()

    child_link_resp = post(
        "/api/links",
        owner_id,
        {
            "url": f"https://cascade-child-{unique}.example.com",
            "name": f"child link {unique}",
            "collectionId": child["id"],
        },
    )
    grandchild_link_resp = post(
        "/api/links",
        owner_id,
        {
            "url": f"https://cascade-grandchild-{unique}.example.com",
            "name": f"grandchild link {unique}",
            "collectionId": grandchild["id"],
        },
    )
    assert child_link_resp.status_code == 201
    assert grandchild_link_resp.status_code == 201
    child_link = child_link_resp.json()
    grandchild_link = grandchild_link_resp.json()

    delete_resp = delete(f"/api/collections/{parent['id']}", owner_id, {"deleteChildren": "true"})
    assert delete_resp.status_code == 200

    assert get(f"/api/collections/{child['id']}", owner_id).status_code == 404
    assert get(f"/api/collections/{grandchild['id']}", owner_id).status_code == 404
    assert get(f"/api/links/{child_link['id']}", owner_id).status_code == 404
    assert get(f"/api/links/{grandchild_link['id']}", owner_id).status_code == 404
