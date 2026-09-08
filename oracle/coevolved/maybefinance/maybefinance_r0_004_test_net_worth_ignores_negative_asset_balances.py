import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_net_worth_ignores_negative_asset_balances():
    h = headers()
    positive_response = requests.post(
        f"{BASE_URL}/accounts",
        json={
            "name": f"PositiveAsset-{uuid.uuid4().hex}",
            "account_type": "depository",
            "balance": 100000,
        },
        headers=h,
        timeout=30,
    )
    assert positive_response.status_code == 201

    negative_response = requests.post(
        f"{BASE_URL}/accounts",
        json={
            "name": f"NegativeAsset-{uuid.uuid4().hex}",
            "account_type": "depository",
            "balance": -25000,
        },
        headers=h,
        timeout=30,
    )
    assert negative_response.status_code == 201

    net_worth_response = requests.get(f"{BASE_URL}/net-worth", headers=h, timeout=30)
    assert net_worth_response.status_code == 200
    data = net_worth_response.json()

    assert data["assets"] == 100000
    assert data["liabilities"] == 0
    assert data["net_worth"] == 100000

    balances_by_id = {account["id"]: account["balance"] for account in data["accounts"]}
    assert positive_response.json()["id"] in balances_by_id
    assert negative_response.json()["id"] in balances_by_id
