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


def test_create_link_rejects_invalid_expires_at():
    slug = f"bad-exp-{uuid.uuid4().hex[:8]}"

    resp = api(
        "POST",
        "/links",
        json={
            "url": "https://example.com/invalid-expiry",
            "slug": slug,
            "expiresAt": "definitely-not-a-date-time",
        },
    )

    assert resp.status_code == 422

    lookup = api("GET", "/links/info", params={"domain": "dub.sh", "slug": slug})
    assert lookup.status_code == 404
