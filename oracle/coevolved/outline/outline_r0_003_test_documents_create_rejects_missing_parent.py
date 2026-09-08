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


def test_documents_create_rejects_missing_parent():
    api("/teams.info")
    collection_response = api(
        "/collections.create",
        {"name": f"drp-missing-parent-{uuid.uuid4().hex}"},
    )
    assert collection_response.status_code == 200, collection_response.text
    collection = collection_response.json()["data"]
    missing_parent_id = str(uuid.uuid4())
    rejected_title = f"drp-orphan-child-{uuid.uuid4().hex}"

    response = api(
        "/documents.create",
        {
            "title": rejected_title,
            "text": "orphan parent probe",
            "collectionId": collection["id"],
            "parentDocumentId": missing_parent_id,
            "publish": True,
        },
    )
    assert response.status_code == 400, response.text

    listed = api("/documents.list", {"collectionId": collection["id"]})
    assert listed.status_code == 200, listed.text
    assert all(document["title"] != rejected_title for document in listed.json()["data"])
