import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def _create_account_and_category(headers, suffix):
    account_resp = requests.post(
        f"{BASE_URL}/accounts",
        json={"name": f"txn-required-acct-{suffix}", "type": "cash", "currency": "USD"},
        headers=headers,
        timeout=30,
    )
    assert account_resp.status_code == 201, account_resp.text

    category_resp = requests.post(
        f"{BASE_URL}/categories",
        json={"name": f"txn-required-cat-{suffix}", "type": "expense"},
        headers=headers,
        timeout=30,
    )
    assert category_resp.status_code == 201, category_resp.text
    return account_resp.json()["id"], category_resp.json()["id"]


def test_transaction_create_requires_date_and_time():
    headers = _headers()
    suffix = uuid.uuid4().hex
    account_id, category_id = _create_account_and_category(headers, suffix)

    missing_date_resp = requests.post(
        f"{BASE_URL}/transactions",
        json={
            "type": "expense",
            "amount": 12.5,
            "accountId": account_id,
            "categoryId": category_id,
            "time": "08:30:00",
            "comment": "missing date should fail",
        },
        headers=headers,
        timeout=30,
    )
    assert missing_date_resp.status_code == 400, missing_date_resp.text

    missing_time_resp = requests.post(
        f"{BASE_URL}/transactions",
        json={
            "type": "expense",
            "amount": 18.75,
            "accountId": account_id,
            "categoryId": category_id,
            "date": "2024-05-06",
            "comment": "missing time should fail",
        },
        headers=headers,
        timeout=30,
    )
    assert missing_time_resp.status_code == 400, missing_time_resp.text

    list_resp = requests.get(
        f"{BASE_URL}/transactions",
        params={"accountId": account_id},
        headers=headers,
        timeout=30,
    )
    assert list_resp.status_code == 200, list_resp.text
    listed = list_resp.json()
    assert listed["total"] == 0
    assert listed["transactions"] == []
