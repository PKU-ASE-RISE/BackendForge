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


def create_document(collection_id, title, parent_id=None):
    body = {
        "title": title,
        "text": f"move cycle probe {uuid.uuid4().hex}",
        "collectionId": collection_id,
        "publish": True,
    }
    if parent_id is not None:
        body["parentDocumentId"] = parent_id
    response = api("/documents.create", body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_documents_move_rejects_parent_cycle():
    api("/teams.info")
    collection_response = api(
        "/collections.create",
        {"name": f"drp-cycle-{uuid.uuid4().hex}"},
    )
    assert collection_response.status_code == 200, collection_response.text
    collection_id = collection_response.json()["data"]["id"]

    parent = create_document(collection_id, f"drp-cycle-parent-{uuid.uuid4().hex}")
    child = create_document(
        collection_id,
        f"drp-cycle-child-{uuid.uuid4().hex}",
        parent_id=parent["id"],
    )

    response = api(
        "/documents.move",
        {
            "id": parent["id"],
            "collectionId": collection_id,
            "parentDocumentId": child["id"],
        },
    )
    assert response.status_code == 400, response.text

    info_response = api("/documents.info", {"id": parent["id"]})
    assert info_response.status_code == 200, info_response.text
    assert info_response.json()["data"]["parentDocumentId"] is None
