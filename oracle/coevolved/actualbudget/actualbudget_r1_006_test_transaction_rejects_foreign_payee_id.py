import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers(user_id):
    return {"X-User-Id": user_id, "Content-Type": "application/json"}


def api(method, path, user_id, json_data=None, params=None):
    return requests.request(
        method,
        f"{BASE_URL}{path}",
        headers=headers(user_id),
        json=json_data,
        params=params,
        timeout=30,
    )


def test_transaction_rejects_foreign_payee_id():
    user_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    suffix = uuid.uuid4().hex

    account_resp = api(
        "POST",
        "/accounts",
        user_id,
        {"name": f"txn-payee-owner-{suffix}", "type": "checking"},
    )
    assert account_resp.status_code == 201, account_resp.text
    account_id = account_resp.json()["id"]

    foreign_payee_resp = api(
        "POST",
        "/payees",
        other_user_id,
        {"name": f"foreign-payee-{suffix}"},
    )
    assert foreign_payee_resp.status_code == 201, foreign_payee_resp.text
    foreign_payee_id = foreign_payee_resp.json()["id"]

    create_resp = api(
        "POST",
        "/transactions",
        user_id,
        {
            "date": "2025-03-02",
            "amount": -2500,
            "accountId": account_id,
            "payeeId": foreign_payee_id,
        },
    )
    assert create_resp.status_code == 400, create_resp.text

    listed_resp = api(
        "GET",
        "/transactions",
        user_id,
        params={"payeeId": foreign_payee_id},
    )
    assert listed_resp.status_code == 200, listed_resp.text
    listed = listed_resp.json()
    assert listed["total"] == 0
    assert listed["data"] == []
