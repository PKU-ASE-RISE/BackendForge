import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def _headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def _post(path, payload, headers):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=headers, timeout=30)


def test_transaction_create_rejects_null_comment():
    headers = _headers()
    unique = uuid.uuid4().hex

    account_resp = _post(
        "/accounts",
        {
            "name": f"null-comment-acct-{unique}",
            "type": "cash",
            "currency": "USD",
        },
        headers,
    )
    assert account_resp.status_code == 201, account_resp.text
    account_id = account_resp.json()["id"]

    category_resp = _post(
        "/categories",
        {"name": f"null-comment-expense-{unique}", "type": "expense"},
        headers,
    )
    assert category_resp.status_code == 201, category_resp.text
    category_id = category_resp.json()["id"]

    create_resp = _post(
        "/transactions",
        {
            "type": "expense",
            "amount": 9.75,
            "accountId": account_id,
            "categoryId": category_id,
            "date": "2024-11-05",
            "time": "08:15:00",
            "comment": None,
        },
        headers,
    )
    assert create_resp.status_code == 400, create_resp.text
    assert "error" in create_resp.json()

    list_resp = requests.get(
        f"{BASE_URL}/transactions",
        params={"accountId": account_id},
        headers=headers,
        timeout=30,
    )
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()
    assert data["total"] == 0
    assert data["transactions"] == []
