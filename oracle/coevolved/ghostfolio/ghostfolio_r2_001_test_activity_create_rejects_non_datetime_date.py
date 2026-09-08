import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_activity_create_rejects_non_datetime_date():
    h = headers()
    marker = f"bad-date-create-{uuid.uuid4().hex}"

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
            "date": "not-a-date-time",
            "quantity": 1,
            "unitPrice": 150,
            "fee": 0,
            "currency": "USD",
            "symbol": "AAPL",
            "accountId": account_id,
            "comment": marker,
        },
        headers=h,
        timeout=30,
    )
    assert create_resp.status_code == 400, create_resp.text

    list_resp = requests.get(f"{BASE_URL}/api/activities", headers=h, timeout=30)
    assert list_resp.status_code == 200, list_resp.text
    assert all(activity.get("comment") != marker for activity in list_resp.json())
