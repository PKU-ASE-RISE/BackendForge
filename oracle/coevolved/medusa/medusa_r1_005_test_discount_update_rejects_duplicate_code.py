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


def test_discount_update_rejects_duplicate_code():
    first_code = unique("DUPA").upper()
    second_code = unique("DUPB").upper()

    first_resp = requests.post(
        url("/admin/discounts"),
        headers=admin_headers(),
        json={"code": first_code, "type": "fixed", "value": 100},
    )
    assert first_resp.status_code == 201

    second_resp = requests.post(
        url("/admin/discounts"),
        headers=admin_headers(),
        json={"code": second_code, "type": "fixed", "value": 200},
    )
    assert second_resp.status_code == 201
    second_id = second_resp.json()["id"]

    duplicate_update = requests.put(
        url(f"/admin/discounts/{second_id}"),
        headers=admin_headers(),
        json={"code": first_code.lower(), "type": "fixed", "value": 200},
    )
    assert 400 <= duplicate_update.status_code < 500, duplicate_update.text

    list_resp = requests.get(url("/admin/discounts"), headers=admin_headers())
    assert list_resp.status_code == 200
    discounts = list_resp.json()["discounts"]
    first_matches = [discount for discount in discounts if discount["code"] == first_code]
    second_matches = [discount for discount in discounts if discount["id"] == second_id]
    assert len(first_matches) == 1
    assert second_matches and second_matches[0]["code"] == second_code
