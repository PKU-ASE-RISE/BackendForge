import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_create_account_requires_balance():
    h = headers()
    name = f"MissingBalance-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/accounts",
        json={"name": name, "account_type": "depository"},
        headers=h,
        timeout=30,
    )

    assert response.status_code == 400
    assert "error" in response.json()

    list_response = requests.get(f"{BASE_URL}/accounts", headers=h, timeout=30)
    assert list_response.status_code == 200
    assert all(account["name"] != name for account in list_response.json())
