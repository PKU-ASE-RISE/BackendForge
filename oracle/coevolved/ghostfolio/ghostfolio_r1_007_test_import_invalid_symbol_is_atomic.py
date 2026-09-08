import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_import_invalid_symbol_is_atomic():
    headers = make_headers()
    account = requests.post(
        f"{BASE_URL}/api/accounts",
        headers=headers,
        json={
            "name": f"import-invalid-symbol-{uuid.uuid4().hex}",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0.0,
        },
        timeout=30,
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]
    marker = f"atomic-invalid-symbol-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/import",
        headers=headers,
        json={
            "activities": [
                {
                    "type": "BUY",
                    "date": "2024-01-05T10:00:00Z",
                    "quantity": 1.0,
                    "unitPrice": 150.0,
                    "fee": 0.0,
                    "currency": "USD",
                    "symbol": "AAPL",
                    "accountId": account_id,
                    "comment": marker,
                },
                {
                    "type": "BUY",
                    "date": "2024-01-06T10:00:00Z",
                    "quantity": 1.0,
                    "unitPrice": 1.0,
                    "fee": 0.0,
                    "currency": "USD",
                    "symbol": f"ZZZ{uuid.uuid4().hex[:8]}",
                    "accountId": account_id,
                    "comment": marker,
                },
            ]
        },
        timeout=30,
    )

    assert response.status_code == 400, response.text

    activities = requests.get(f"{BASE_URL}/api/activities", headers=headers, timeout=30)
    assert activities.status_code == 200, activities.text
    assert all(activity.get("comment") != marker for activity in activities.json())
