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


def test_discount_create_rejects_invalid_type():
    code = unique("BADTYPE").upper()
    resp = requests.post(
        url("/admin/discounts"),
        headers=admin_headers(),
        json={"code": code, "type": "bogus", "value": 10},
    )

    assert 400 <= resp.status_code < 500, resp.text

    list_resp = requests.get(url("/admin/discounts"), headers=admin_headers())
    assert list_resp.status_code == 200
    assert all(discount["code"] != code for discount in list_resp.json()["discounts"])
