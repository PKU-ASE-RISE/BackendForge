import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_import_rejects_non_datetime_date_atomically():
    h = headers()
    good_marker = f"import-good-{uuid.uuid4().hex}"
    bad_marker = f"import-bad-date-{uuid.uuid4().hex}"

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

    import_resp = requests.post(
        f"{BASE_URL}/api/import",
        json={
            "activities": [
                {
                    "type": "BUY",
                    "date": "2024-02-01T09:30:00Z",
                    "quantity": 1,
                    "unitPrice": 140,
                    "fee": 0,
                    "currency": "USD",
                    "symbol": "GOOGL",
                    "accountId": account_id,
                    "comment": good_marker,
                },
                {
                    "type": "BUY",
                    "date": "not-a-date-time",
                    "quantity": 1,
                    "unitPrice": 150,
                    "fee": 0,
                    "currency": "USD",
                    "symbol": "AAPL",
                    "accountId": account_id,
                    "comment": bad_marker,
                },
            ]
        },
        headers=h,
        timeout=30,
    )
    assert import_resp.status_code == 400, import_resp.text

    export_resp = requests.get(f"{BASE_URL}/api/export", headers=h, timeout=30)
    assert export_resp.status_code == 200, export_resp.text
    comments = {activity.get("comment") for activity in export_resp.json()["activities"]}
    assert good_marker not in comments
    assert bad_marker not in comments
