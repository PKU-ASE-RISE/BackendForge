import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"expense-amount-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_expense_amount_must_be_numeric():
    response = requests.post(
        f"{BASE_URL}/api/expenses",
        json={
            "vendor": f"vendor-{uuid.uuid4().hex}",
            "category": "software",
            "amount": "not-a-number",
            "date": "2024-04-01",
        },
        headers=headers(),
        timeout=30,
    )

    assert response.status_code == 422
    assert "error" in response.json()
