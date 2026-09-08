import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def api_post(path, payload, h):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=h, timeout=30)


def api_get(path, h):
    return requests.get(f"{BASE_URL}{path}", headers=h, timeout=30)


def test_payee_rejects_foreign_default_category():
    owner_headers = make_headers()
    other_headers = make_headers()
    unique = uuid.uuid4().hex

    group_resp = api_post("/category-groups", {"name": f"PayeeOwnerGroup-{unique}"}, owner_headers)
    assert group_resp.status_code == 201, group_resp.text
    category_resp = api_post(
        "/categories",
        {"name": f"PayeeOwnerCategory-{unique}", "groupId": group_resp.json()["id"]},
        owner_headers,
    )
    assert category_resp.status_code == 201, category_resp.text
    foreign_category_id = category_resp.json()["id"]

    payee_resp = api_post(
        "/payees",
        {"name": f"ForeignDefaultPayee-{unique}", "categoryId": foreign_category_id},
        other_headers,
    )
    assert payee_resp.status_code == 400, payee_resp.text

    other_payees = api_get("/payees", other_headers)
    assert other_payees.status_code == 200, other_payees.text
    assert all(payee["name"] != f"ForeignDefaultPayee-{unique}" for payee in other_payees.json())
