import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_activity_update_rejects_non_datetime_date():
    h = headers()
    original_date = "2024-01-15T10:00:00Z"

    account_resp = requests.post(
        f"{BASE_URL}/api/accounts",
        json={
            "name": f"acct-{uuid.uuid4().hex}",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0,
        },
        headers=h,
        timeout=30,
    )
    assert account_resp.status_code == 201, account_resp.text
    account_id = account_resp.json()["id"]

    create_resp = requests.post(
        f"{BASE_URL}/api/activities",
        json={
            "type": "BUY",
            "date": original_date,
            "quantity": 2,
            "unitPrice": 150,
            "fee": 0,
            "currency": "USD",
            "symbol": "AAPL",
            "accountId": account_id,
            "comment": f"valid-before-update-{uuid.uuid4().hex}",
        },
        headers=h,
        timeout=30,
    )
    assert create_resp.status_code == 201, create_resp.text
    activity_id = create_resp.json()["id"]

    update_resp = requests.put(
        f"{BASE_URL}/api/activities/{activity_id}",
        json={"date": "31-31-2024 definitely invalid"},
        headers=h,
        timeout=30,
    )
    assert update_resp.status_code == 400, update_resp.text

    get_resp = requests.get(f"{BASE_URL}/api/activities/{activity_id}", headers=h, timeout=30)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["date"] == original_date
