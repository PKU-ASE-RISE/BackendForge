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


def unique(prefix):
    return f"{prefix}{uuid.uuid4().hex}"


def ensure_admin():
    response = api("/teams.info")
    assert response.status_code == 200, response.text


def create_collection(prefix):
    response = api("/collections.create", {"name": unique(prefix)})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def create_document(collection_id):
    response = api(
        "/documents.create",
        {
            "title": unique("pin-cross-doc-"),
            "text": "document should only be pinnable in its own collection",
            "collectionId": collection_id,
            "publish": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_pins_create_rejects_cross_collection_document():
    ensure_admin()
    document_collection = create_collection("pin-doc-col-")
    other_collection = create_collection("pin-other-col-")
    document = create_document(document_collection["id"])

    response = api(
        "/pins.create",
        {"documentId": document["id"], "collectionId": other_collection["id"], "index": 0},
    )

    assert response.status_code in (400, 404), response.text

    listed = api("/pins.list", {"collectionId": other_collection["id"]})
    assert listed.status_code == 200, listed.text
    pin_document_ids = [pin["documentId"] for pin in listed.json()["data"]]
    assert document["id"] not in pin_document_ids
