import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_ROOT = "/api"
WORKSPACES = API_ROOT + "/workspaces"
ADMIN_KEY = "admin-key-001"


def api(method, path, key=ADMIN_KEY, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = key
    kwargs.setdefault("timeout", 30)
    return getattr(requests, method)(f"{BASE_URL}{path}", headers=headers, **kwargs)


def test_workspace_slug_pattern_rejected():
    bad_slug = f"Bad_Slug_{uuid.uuid4().hex[:6]}"
    response = api("post", WORKSPACES, json={"name": "Invalid Slug", "slug": bad_slug})
    assert response.status_code in (400, 422), response.text
