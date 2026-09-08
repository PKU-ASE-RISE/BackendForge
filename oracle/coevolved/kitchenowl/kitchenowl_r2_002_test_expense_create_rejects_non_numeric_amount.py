import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")


def headers(user_id, household_id):
    return {
        "X-User-Id": user_id,
        "X-Household-Id": household_id,
        "Content-Type": "application/json",
    }


def test_expense_create_rejects_non_numeric_amount():
    household_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    h = headers(user_id, household_id)
    marker = f"bad-amount-{uuid.uuid4().hex}"

    membership_response = requests.get(
        f"{BASE_URL}/api/households", headers=h, timeout=30
    )

    response = requests.post(
        f"{BASE_URL}/api/expenses",
        json={
            "amount": "not-a-number",
            "description": marker,
            "date": "2026-02-10",
            "paidBy": user_id,
            "splitBetween": [user_id],
        },
        headers=h,
        timeout=30,
    )
    expenses_after_response = requests.get(
        f"{BASE_URL}/api/expenses", headers=h, timeout=30
    )
    expenses_after = expenses_after_response.json()

    assert response.status_code == 400
    assert all(expense["description"] != marker for expense in expenses_after)
