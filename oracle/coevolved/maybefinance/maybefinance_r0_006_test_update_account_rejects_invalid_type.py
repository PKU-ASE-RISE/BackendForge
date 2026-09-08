import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_update_account_rejects_invalid_type():
    h = headers()
    create_response = requests.post(
        f"{BASE_URL}/accounts",
        json={
            "name": f"Acct-{uuid.uuid4().hex}",
            "account_type": "depository",
            "balance": 12345,
        },
        headers=h,
        timeout=30,
    )
    assert create_response.status_code == 201
    account_id = create_response.json()["id"]

    update_response = requests.put(
        f"{BASE_URL}/accounts/{account_id}",
        json={"account_type": "not_a_real_type"},
        headers=h,
        timeout=30,
    )

    assert update_response.status_code == 400
    assert "error" in update_response.json()

    get_response = requests.get(f"{BASE_URL}/accounts/{account_id}", headers=h, timeout=30)
    assert get_response.status_code == 200
    assert get_response.json()["account_type"] == "depository"
