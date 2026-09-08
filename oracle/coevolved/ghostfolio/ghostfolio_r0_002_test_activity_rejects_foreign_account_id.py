import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def make_headers(user_id=None):
    return {"X-User-Id": user_id or str(uuid.uuid4()), "Content-Type": "application/json"}


def test_activity_rejects_foreign_account_id():
    owner_headers = make_headers()
    attacker_headers = make_headers()
    account_response = requests.post(
        f"{BASE_URL}/api/accounts",
        json={
            "name": f"owner-account-{uuid.uuid4().hex}",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0,
        },
        headers=owner_headers,
        timeout=30,
    )
    assert account_response.status_code == 201
    foreign_account_id = account_response.json()["id"]
    marker = f"foreign-account-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/activities",
        json={
            "type": "BUY",
            "date": "2024-03-01T00:00:00Z",
            "quantity": 1,
            "unitPrice": 150.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "AAPL",
            "accountId": foreign_account_id,
            "comment": marker,
        },
        headers=attacker_headers,
        timeout=30,
    )

    assert response.status_code == 400
    assert "error" in response.json()

    attacker_activities = requests.get(f"{BASE_URL}/api/activities", headers=attacker_headers, timeout=30)
    assert attacker_activities.status_code == 200
    assert all(activity.get("comment") != marker for activity in attacker_activities.json())

    owner_account = requests.get(f"{BASE_URL}/api/accounts/{foreign_account_id}", headers=owner_headers, timeout=30)
    assert owner_account.status_code == 200
    assert owner_account.json().get("transactionCount", 0) == 0
