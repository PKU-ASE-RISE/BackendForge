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


def test_create_tag_rejects_non_hex_color():
    name = f"bad-color-{uuid.uuid4().hex[:8]}"

    resp = api("POST", "/tags", json={"name": name, "color": "not-a-hex-color"})
    listed = api("GET", "/tags")

    assert resp.status_code == 422
    assert listed.status_code == 200
    assert name not in {tag["name"] for tag in listed.json()}
