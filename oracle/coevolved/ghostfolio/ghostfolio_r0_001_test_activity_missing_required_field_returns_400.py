import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_activity_missing_required_field_returns_400():
    user_headers = headers()
    account_response = requests.post(
        f"{BASE_URL}/api/accounts",
        json={
            "name": f"missing-required-{uuid.uuid4().hex}",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0,
        },
        headers=user_headers,
        timeout=30,
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]
    marker = f"missing-quantity-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/activities",
        json={
            "type": "BUY",
            "date": "2024-01-01T00:00:00Z",
            "unitPrice": 150.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "AAPL",
            "accountId": account_id,
            "comment": marker,
        },
        headers=user_headers,
        timeout=30,
    )

    assert response.status_code == 400
    data = response.json()
    assert "error" in data

    list_response = requests.get(f"{BASE_URL}/api/activities", headers=user_headers, timeout=30)
    assert list_response.status_code == 200
    assert all(activity.get("comment") != marker for activity in list_response.json())
