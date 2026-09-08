import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def api_post(path, payload, headers):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_put(path, payload, headers):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_get(path, headers):
    return requests.get(f"{BASE_URL}{path}", headers=headers, timeout=30)


def test_account_update_requires_full_required_fields():
    headers = make_headers()
    unique = uuid.uuid4().hex
    created_resp = api_post(
        "/accounts",
        {
            "name": f"acct-required-{unique}",
            "type": "checking",
            "currency": "USD",
            "icon": "original-icon",
            "displayOrder": 3,
        },
        headers,
    )
    assert created_resp.status_code == 201, created_resp.text
    account_id = created_resp.json()["id"]

    update_resp = api_put(
        f"/accounts/{account_id}",
        {"icon": "changed-without-required-fields", "displayOrder": 99},
        headers,
    )
    assert update_resp.status_code == 400, update_resp.text

    fetched_resp = api_get(f"/accounts/{account_id}", headers)
    assert fetched_resp.status_code == 200, fetched_resp.text
    fetched = fetched_resp.json()
    assert fetched["name"] == f"acct-required-{unique}"
    assert fetched["type"] == "checking"
    assert fetched["currency"] == "USD"
    assert fetched["icon"] == "original-icon"
    assert fetched["displayOrder"] == 3
