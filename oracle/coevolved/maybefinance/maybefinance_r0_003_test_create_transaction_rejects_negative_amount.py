import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_create_transaction_rejects_negative_amount():
    h = headers()
    account_response = requests.post(
        f"{BASE_URL}/accounts",
        json={
            "name": f"TxnAcct-{uuid.uuid4().hex}",
            "account_type": "depository",
            "balance": 50000,
        },
        headers=h,
        timeout=30,
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]
    txn_name = f"NegativeTxn-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/transactions",
        json={
            "account_id": account_id,
            "date": "2026-03-15",
            "amount": -100,
            "name": txn_name,
        },
        headers=h,
        timeout=30,
    )

    assert response.status_code == 400
    assert "error" in response.json()

    list_response = requests.get(
        f"{BASE_URL}/transactions",
        params={"account_id": account_id},
        headers=h,
        timeout=30,
    )
    assert list_response.status_code == 200
    assert all(transaction["name"] != txn_name for transaction in list_response.json())
