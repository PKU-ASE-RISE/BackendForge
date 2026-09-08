import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def post(path, payload, h):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=h, timeout=30)


def get(path, h, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=h, timeout=30)


def test_create_transaction_rejects_non_array_tags():
    h = headers()
    suffix = uuid.uuid4().hex
    account = post(
        "/accounts",
        {
            "name": f"TagsAccount-{suffix}",
            "account_type": "depository",
            "balance": 10000,
        },
        h,
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]
    txn_name = f"BadTags-{suffix}"

    rejected = post(
        "/transactions",
        {
            "account_id": account_id,
            "date": "2026-04-17",
            "amount": 1200,
            "name": txn_name,
            "tags": "",
        },
        h,
    )
    assert rejected.status_code == 400, rejected.text
    assert "error" in rejected.json()

    transactions = get("/transactions", h, params={"account_id": account_id})
    assert transactions.status_code == 200, transactions.text
    assert txn_name not in {txn["name"] for txn in transactions.json()}
