import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {"X-Api-Key": "admin-user-key", "Content-Type": "application/json"}
VIEWER_KEY = f"viewer-info-draft-{uuid.uuid4().hex}"
VIEWER_HEADERS = {"X-Api-Key": VIEWER_KEY, "Content-Type": "application/json"}


def api(path, body=None, headers=None):
    return requests.post(
        f"{BASE_URL}{path}",
        json={} if body is None else body,
        headers=ADMIN_HEADERS if headers is None else headers,
        timeout=30,
    )


def ensure_admin():
    response = api("/teams.info")
    assert response.status_code == 200, response.text


def ensure_viewer():
    ensure_admin()
    created = api("/teams.info", headers=VIEWER_HEADERS)
    assert created.status_code == 200, created.text
    users = api("/users.list")
    assert users.status_code == 200, users.text
    viewer = next(user for user in users.json()["data"] if user["name"] == VIEWER_KEY)
    updated = api("/users.update", {"id": viewer["id"], "role": "viewer"})
    assert updated.status_code == 200, updated.text


def create_collection():
    response = api("/collections.create", {"name": f"draft-viewer-{uuid.uuid4().hex}"})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_documents_info_hides_drafts_from_viewer():
    ensure_viewer()
    collection = create_collection()
    draft = api(
        "/documents.create",
        {
            "title": f"private-draft-{uuid.uuid4().hex}",
            "text": "unpublished viewer-hidden text",
            "collectionId": collection["id"],
            "publish": False,
        },
    )
    assert draft.status_code == 200, draft.text
    document_id = draft.json()["data"]["id"]

    viewer_response = api("/documents.info", {"id": document_id}, headers=VIEWER_HEADERS)
    assert viewer_response.status_code == 404, viewer_response.text

    admin_response = api("/documents.info", {"id": document_id})
    assert admin_response.status_code == 200, admin_response.text
    assert admin_response.json()["data"]["publishedAt"] is None
