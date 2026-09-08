import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30
ADMIN_KEY = "admin_ws1_user2"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = dict(kwargs.pop("headers", {}) or {})
    if key:
        headers["X-API-Key"] = key
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    return requests.request(method, f"{BASE_URL}{path}", headers=headers, **kwargs)


def test_update_link_rejects_invalid_expires_at_without_mutating():
    slug = f"upd-exp-{uuid.uuid4().hex[:8]}"
    create = api("POST", "/links", json={"url": "https://example.com/update-expiry", "slug": slug})
    assert create.status_code == 201
    link_id = create.json()["id"]
    original_expires_at = create.json().get("expiresAt")

    update = api("PUT", f"/links/{link_id}", json={"expiresAt": "not-an-iso-datetime"})
    reloaded = api("GET", f"/links/{link_id}")

    assert update.status_code == 422
    assert reloaded.status_code == 200
    assert reloaded.json().get("expiresAt") == original_expires_at
