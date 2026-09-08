import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_activity_rejects_foreign_tag_id():
    owner_headers = make_headers()
    attacker_headers = make_headers()

    tag_response = requests.post(
        f"{BASE_URL}/api/tags",
        json={"name": f"private-tag-{uuid.uuid4().hex}"},
        headers=owner_headers,
        timeout=30,
    )
    assert tag_response.status_code == 201
    foreign_tag_id = tag_response.json()["id"]

    account_response = requests.post(
        f"{BASE_URL}/api/accounts",
        json={
            "name": f"attacker-account-{uuid.uuid4().hex}",
            "accountType": "SECURITIES",
            "currency": "USD",
            "balance": 0,
        },
        headers=attacker_headers,
        timeout=30,
    )
    assert account_response.status_code == 201
    account_id = account_response.json()["id"]
    marker = f"foreign-tag-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/activities",
        json={
            "type": "BUY",
            "date": "2024-04-01T00:00:00Z",
            "quantity": 1,
            "unitPrice": 400.0,
            "fee": 0,
            "currency": "USD",
            "symbol": "MSFT",
            "accountId": account_id,
            "comment": marker,
            "tagIds": [foreign_tag_id],
        },
        headers=attacker_headers,
        timeout=30,
    )

    assert response.status_code == 400
    assert "error" in response.json()

    activities_response = requests.get(f"{BASE_URL}/api/activities", headers=attacker_headers, timeout=30)
    assert activities_response.status_code == 200
    assert all(activity.get("comment") != marker for activity in activities_response.json())
