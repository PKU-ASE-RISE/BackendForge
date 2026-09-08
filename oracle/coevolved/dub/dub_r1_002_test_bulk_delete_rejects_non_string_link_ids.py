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


def test_bulk_delete_rejects_non_string_link_ids():
    slug = f"bulk-del-type-{uuid.uuid4().hex[:8]}"
    create = api("POST", "/links", json={"url": "https://example.com/bulk-delete-type", "slug": slug})
    assert create.status_code == 201
    link_id = create.json()["id"]

    delete = api("DELETE", "/links/bulk", json={"linkIds": [link_id, 123456]})
    reloaded = api("GET", f"/links/{link_id}")

    assert delete.status_code == 422
    assert reloaded.status_code == 200
    assert reloaded.json()["id"] == link_id
