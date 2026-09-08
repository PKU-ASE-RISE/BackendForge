import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {"X-Api-Key": "admin-user-key", "Content-Type": "application/json"}


def api(path, body=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if body is None else body,
        headers=ADMIN_HEADERS,
        timeout=30,
    )


def create_collection(label):
    response = api("/collections.create", {"name": f"drp-{label}-{uuid.uuid4().hex}"})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def create_document(collection_id, title, parent_id=None):
    body = {
        "title": title,
        "text": f"hierarchy validation {uuid.uuid4().hex}",
        "collectionId": collection_id,
        "publish": True,
    }
    if parent_id is not None:
        body["parentDocumentId"] = parent_id
    response = api("/documents.create", body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_documents_create_rejects_cross_collection_parent():
    api("/teams.info")
    collection_a = create_collection("parent-col")
    collection_b = create_collection("child-col")
    parent = create_document(
        collection_a["id"],
        f"drp-parent-{uuid.uuid4().hex}",
    )
    child_title = f"drp-cross-parent-child-{uuid.uuid4().hex}"

    response = api(
        "/documents.create",
        {
            "title": child_title,
            "text": "this child should be rejected",
            "collectionId": collection_b["id"],
            "parentDocumentId": parent["id"],
            "publish": True,
        },
    )
    assert response.status_code == 400, response.text

    listed = api("/documents.list", {"collectionId": collection_b["id"]})
    assert listed.status_code == 200, listed.text
    assert all(document["title"] != child_title for document in listed.json()["data"])
