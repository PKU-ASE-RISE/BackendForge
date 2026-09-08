import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_account_update_requires_required_fields():
    headers = _headers()
    suffix = uuid.uuid4().hex

    create_resp = requests.post(
        f"{BASE_URL}/accounts",
        json={
            "name": f"acct-required-{suffix}",
            "type": "checking",
            "currency": "USD",
            "icon": "bank",
            "displayOrder": 4,
        },
        headers=headers,
        timeout=30,
    )
    assert create_resp.status_code == 201, create_resp.text
    account = create_resp.json()

    partial_update_resp = requests.put(
        f"{BASE_URL}/accounts/{account['id']}",
        json={"name": f"acct-renamed-{suffix}"},
        headers=headers,
        timeout=30,
    )

    fetched_resp = requests.get(
        f"{BASE_URL}/accounts/{account['id']}",
        headers=headers,
        timeout=30,
    )
    assert fetched_resp.status_code == 200, fetched_resp.text
    fetched = fetched_resp.json()

    assert partial_update_resp.status_code == 400, partial_update_resp.text
    assert fetched["name"] == account["name"]
    assert fetched["type"] == "checking"
    assert fetched["currency"] == "USD"
