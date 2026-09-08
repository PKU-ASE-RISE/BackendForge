import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def api_post(path, payload, headers):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def api_get(path, headers, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=headers, timeout=30)


def test_transaction_rejects_malformed_date_time():
    headers = make_headers()
    unique = uuid.uuid4().hex
    account_resp = api_post(
        "/accounts",
        {"name": f"date-time-acct-{unique}", "type": "cash", "currency": "USD"},
        headers,
    )
    assert account_resp.status_code == 201, account_resp.text
    account_id = account_resp.json()["id"]
    category_resp = api_post(
        "/categories",
        {"name": f"date-time-cat-{unique}", "type": "expense"},
        headers,
    )
    assert category_resp.status_code == 201, category_resp.text
    category_id = category_resp.json()["id"]

    bad_date_resp = api_post(
        "/transactions",
        {
            "type": "expense",
            "amount": 12.34,
            "accountId": account_id,
            "categoryId": category_id,
            "date": "2024/03/15",
            "time": "10:00:00",
            "comment": f"bad-date-{unique}",
        },
        headers,
    )
    assert bad_date_resp.status_code == 400, bad_date_resp.text

    bad_time_resp = api_post(
        "/transactions",
        {
            "type": "expense",
            "amount": 56.78,
            "accountId": account_id,
            "categoryId": category_id,
            "date": "2024-03-15",
            "time": "25:61:61",
            "comment": f"bad-time-{unique}",
        },
        headers,
    )
    assert bad_time_resp.status_code == 400, bad_time_resp.text

    listed_resp = api_get("/transactions", headers, params={"accountId": account_id})
    assert listed_resp.status_code == 200, listed_resp.text
    listed = listed_resp.json()
    comments = {txn["comment"] for txn in listed["transactions"]}
    assert f"bad-date-{unique}" not in comments
    assert f"bad-time-{unique}" not in comments
