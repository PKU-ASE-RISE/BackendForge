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


def test_link_creator_cannot_move_after_losing_source_write():
    owner_id = str(uuid.uuid4())
    collaborator_id = str(uuid.uuid4())
    unique = uuid.uuid4().hex

    collaborator_collections = get("/api/collections", collaborator_id)
    assert collaborator_collections.status_code == 200
    collaborator_unorganized = next(
        collection
        for collection in collaborator_collections.json()["collections"]
        if collection["ownerId"] == collaborator_id and collection["name"] == "Unorganized"
    )

    collection_resp = post("/api/collections", owner_id, {"name": f"source-write-{unique}"})
    assert collection_resp.status_code == 201
    collection = collection_resp.json()

    member_resp = post(
        f"/api/collections/{collection['id']}/members",
        owner_id,
        {"userId": collaborator_id, "role": "contributor"},
    )
    assert member_resp.status_code == 201
    member = member_resp.json()

    link_resp = post(
        "/api/links",
        collaborator_id,
        {
            "url": f"https://demoted-move-{unique}.example.com",
            "name": f"demoted move {unique}",
            "collectionId": collection["id"],
        },
    )
    assert link_resp.status_code == 201
    link = link_resp.json()
    assert link["createdBy"] == collaborator_id
    assert link["collectionId"] == collection["id"]

    demote_resp = put(
        f"/api/collections/{collection['id']}/members/{member['id']}",
        owner_id,
        {"role": "viewer"},
    )
    assert demote_resp.status_code == 200
    assert demote_resp.json()["role"] == "viewer"

    move_resp = put(
        f"/api/links/{link['id']}",
        collaborator_id,
        {"collectionId": collaborator_unorganized["id"]},
    )
    assert move_resp.status_code == 403

    reloaded_resp = get(f"/api/links/{link['id']}", owner_id)
    assert reloaded_resp.status_code == 200
    assert reloaded_resp.json()["collectionId"] == collection["id"]
