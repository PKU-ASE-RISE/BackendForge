import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def post(path, payload, h):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=h, timeout=30)


def get(path, h):
    return requests.get(f"{BASE_URL}{path}", headers=h, timeout=30)


def test_create_holding_rejects_non_integer_values():
    h = headers()
    suffix = uuid.uuid4().hex
    account = post(
        "/accounts",
        {
            "name": f"InvestBadHolding-{suffix}",
            "account_type": "investment",
            "balance": 25000,
        },
        h,
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]
    symbol = f"BAD{suffix[:6].upper()}"

    rejected = post(
        f"/accounts/{account_id}/holdings",
        {
            "symbol": symbol,
            "shares": 2.5,
            "cost_basis": 15000,
            "current_value": "not-cents",
        },
        h,
    )
    assert rejected.status_code == 400, rejected.text
    assert "error" in rejected.json()

    holdings = get(f"/accounts/{account_id}/holdings", h)
    assert holdings.status_code == 200, holdings.text
    assert symbol not in {holding["symbol"] for holding in holdings.json()}
