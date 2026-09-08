import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"
ADMIN_KEY = "admin_direct_probe"


def url(path):
    return f"{BASE_URL}{path}"


def admin_headers():
    return {"X-API-Key": ADMIN_KEY, "Content-Type": "application/json"}


def unique(prefix):
    return f"{prefix}{uuid.uuid4().hex}"


def test_product_create_rejects_invalid_status():
    resp = requests.post(
        url("/admin/products"),
        headers=admin_headers(),
        json={
            "title": "Invalid Status Product",
            "handle": unique("invalid-status-"),
            "status": "archived",
        },
    )

    assert 400 <= resp.status_code < 500, resp.text
