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


def test_collections_create_rejects_invalid_sort_field():
    ensure_admin()
    name = f"invalid-sort-field-{uuid.uuid4().hex}"

    response = api(
        "/collections.create",
        {
            "name": name,
            "sort": {"field": "updated_at", "direction": "asc"},
        },
    )

    assert response.status_code == 400, response.text

    listed = api("/collections.list", {"limit": 100})
    assert listed.status_code == 200, listed.text
    names = {collection["name"] for collection in listed.json()["data"]}
    assert name not in names
