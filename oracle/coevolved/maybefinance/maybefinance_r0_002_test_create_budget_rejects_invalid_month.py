import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def test_create_budget_rejects_invalid_month():
    h = headers()
    category_response = requests.post(
        f"{BASE_URL}/categories",
        json={
            "name": f"BudgetCat-{uuid.uuid4().hex}",
            "color": "#224466",
            "category_type": "expense",
        },
        headers=h,
        timeout=30,
    )
    assert category_response.status_code == 201
    category_id = category_response.json()["id"]

    response = requests.post(
        f"{BASE_URL}/budgets",
        json={
            "category_id": category_id,
            "month": 13,
            "year": 2026,
            "amount": 50000,
        },
        headers=h,
        timeout=30,
    )

    assert response.status_code == 400
    assert "error" in response.json()

    budgets_response = requests.get(f"{BASE_URL}/budgets", headers=h, timeout=30)
    assert budgets_response.status_code == 200
    assert all(budget["category_id"] != category_id for budget in budgets_response.json())
