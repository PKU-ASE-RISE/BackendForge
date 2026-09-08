import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(user_id=None):
    return {"X-User-Id": user_id or str(uuid.uuid4()), "Content-Type": "application/json"}


def test_sync_rejects_foreign_category():
    owner_headers = headers()
    other_headers = headers()

    account_response = requests.post(
        f"{BASE_URL}/accounts",
        json={
            "name": f"SyncAcct-{uuid.uuid4().hex}",
            "account_type": "depository",
            "balance": 80000,
        },
        headers=owner_headers,
        timeout=30,
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]

    foreign_category_response = requests.post(
        f"{BASE_URL}/categories",
        json={
            "name": f"ForeignCat-{uuid.uuid4().hex}",
            "color": "#AA0000",
            "category_type": "expense",
        },
        headers=other_headers,
        timeout=30,
    )
    assert foreign_category_response.status_code == 201
    foreign_category_id = foreign_category_response.json()["id"]
    txn_name = f"CrossUserSyncTxn-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/accounts/{account_id}/syncs",
        json={
            "balance": 70000,
            "transactions": [
                {
                    "date": "2026-04-02",
                    "amount": 10000,
                    "name": txn_name,
                    "category_id": foreign_category_id,
                }
            ],
        },
        headers=owner_headers,
        timeout=30,
    )

    assert response.status_code == 400
    assert "error" in response.json()

    account_after = requests.get(f"{BASE_URL}/accounts/{account_id}", headers=owner_headers, timeout=30)
    assert account_after.status_code == 200
    assert account_after.json()["balance"] == 80000

    transactions_after = requests.get(
        f"{BASE_URL}/transactions",
        params={"account_id": account_id},
        headers=owner_headers,
        timeout=30,
    )
    assert transactions_after.status_code == 200
    assert all(transaction["name"] != txn_name for transaction in transactions_after.json())
