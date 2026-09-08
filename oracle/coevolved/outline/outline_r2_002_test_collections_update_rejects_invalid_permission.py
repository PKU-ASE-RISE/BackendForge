import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_HEADERS = {"X-Api-Key": "admin-user-key", "Content-Type": "application/json"}


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


def create_collection():
    response = api(
        "/collections.create",
        {"name": f"permission-update-{uuid.uuid4().hex}", "permission": "read_write"},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_collections_update_rejects_invalid_permission():
    ensure_admin()
    collection = create_collection()

    response = api(
        "/collections.update",
        {"id": collection["id"], "permission": "read_only"},
    )

    assert response.status_code == 400, response.text

    reloaded = api("/collections.info", {"id": collection["id"]})
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["data"]["permission"] == "read_write"
