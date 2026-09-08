import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def _create_account_and_category(headers, suffix):
    account_resp = requests.post(
        f"{BASE_URL}/accounts",
        json={"name": f"txn-format-acct-{suffix}", "type": "checking", "currency": "USD"},
        headers=headers,
        timeout=30,
    )
    assert account_resp.status_code == 201, account_resp.text

    category_resp = requests.post(
        f"{BASE_URL}/categories",
        json={"name": f"txn-format-cat-{suffix}", "type": "income"},
        headers=headers,
        timeout=30,
    )
    assert category_resp.status_code == 201, category_resp.text
    return account_resp.json()["id"], category_resp.json()["id"]


def test_transaction_rejects_invalid_date_time_format():
    headers = _headers()
    suffix = uuid.uuid4().hex
    account_id, category_id = _create_account_and_category(headers, suffix)

    invalid_resp = requests.post(
        f"{BASE_URL}/transactions",
        json={
            "type": "income",
            "amount": 100.0,
            "accountId": account_id,
            "categoryId": category_id,
            "date": "2024/05/06",
            "time": "25:61:00",
            "comment": "bad date and time format",
        },
        headers=headers,
        timeout=30,
    )
    assert invalid_resp.status_code == 400, invalid_resp.text

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
