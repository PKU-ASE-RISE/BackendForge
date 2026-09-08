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


def test_expense_update_rejects_invalid_date():
    household_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    h = headers(user_id, household_id)
    marker = f"date-update-{uuid.uuid4().hex}"
    original_date = "2026-03-14"

    membership_response = requests.get(
        f"{BASE_URL}/api/households", headers=h, timeout=30
    )
    created = requests.post(
        f"{BASE_URL}/api/expenses",
        json={
            "amount": 18.75,
            "description": marker,
            "date": original_date,
            "paidBy": user_id,
            "splitBetween": [user_id],
        },
        headers=h,
        timeout=30,
    )
    assert created.status_code == 201
    expense_id = created.json()["id"]

    response = requests.put(
        f"{BASE_URL}/api/expenses/{expense_id}",
        json={"date": "03/14/2026"},
        headers=h,
        timeout=30,
    )
    expenses_after_response = requests.get(
        f"{BASE_URL}/api/expenses", headers=h, timeout=30
    )
    expenses_after = expenses_after_response.json()
    reloaded = next(expense for expense in expenses_after if expense["id"] == expense_id)

    assert response.status_code == 400
    assert reloaded["date"] == original_date
