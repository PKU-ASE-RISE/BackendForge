import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_delete_account_with_activity_returns_400():
    user_headers = headers()
    account_response = requests.post(
        f"{BASE_URL}/api/accounts",
        json={
            "name": f"referenced-account-{uuid.uuid4().hex}",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0,
        },
        headers=user_headers,
        timeout=30,
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]

    activity_response = requests.post(
        f"{BASE_URL}/api/activities",
        json={
            "type": "BUY",
            "date": "2024-05-01T00:00:00Z",
            "quantity": 2,
            "unitPrice": 150.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "AAPL",
            "accountId": account_id,
        },
        headers=user_headers,
        timeout=30,
    )
    assert activity_response.status_code == 201
    activity_id = activity_response.json()["id"]

    response = requests.delete(f"{BASE_URL}/api/accounts/{account_id}", headers=user_headers, timeout=30)

    assert response.status_code == 400
    assert "error" in response.json()

    account_after = requests.get(f"{BASE_URL}/api/accounts/{account_id}", headers=user_headers, timeout=30)
    assert account_after.status_code == 200
    activity_after = requests.get(f"{BASE_URL}/api/activities/{activity_id}", headers=user_headers, timeout=30)
    assert activity_after.status_code == 200
