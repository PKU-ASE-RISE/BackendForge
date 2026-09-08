import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {"X-Api-Key": "admin-user-key", "Content-Type": "application/json"}
MEMBER_HEADERS = {
    "X-Api-Key": f"member-move-read-source-{uuid.uuid4().hex}",
    "Content-Type": "application/json",
}


def api(path, body=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if body is None else body,
        headers=ADMIN_HEADERS if headers is None else headers,
        timeout=30,
    )


def ensure_users():
    admin = api("/teams.info")
    assert admin.status_code == 200, admin.text
    member = api("/teams.info", headers=MEMBER_HEADERS)
    assert member.status_code == 200, member.text


def create_collection(permission):
    response = api(
        "/collections.create",
        {"name": f"{permission}-move-{uuid.uuid4().hex}", "permission": permission},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def create_document(collection_id):
    response = api(
        "/documents.create",
        {
            "title": f"read-source-doc-{uuid.uuid4().hex}",
            "text": "member must not move this out of read collection",
            "collectionId": collection_id,
            "publish": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_documents_move_from_read_collection_forbidden_for_member():
    ensure_users()
    read_collection = create_collection("read")
    write_collection = create_collection("read_write")
    document = create_document(read_collection["id"])

    moved = api(
        "/documents.move",
        {"id": document["id"], "collectionId": write_collection["id"]},
        headers=MEMBER_HEADERS,
    )

    assert moved.status_code == 403, moved.text

    reloaded = api("/documents.info", {"id": document["id"]})
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["data"]["collectionId"] == read_collection["id"]
