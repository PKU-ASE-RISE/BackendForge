import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-User-Id": str(uuid.uuid4()), "Content-Type": "application/json"}


def post(path, payload, h):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=h, timeout=30)


def put(path, payload, h):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=h, timeout=30)


def get(path, h):
    return requests.get(f"{BASE_URL}{path}", headers=h, timeout=30)


def test_update_budget_rejects_non_integer_amount():
    h = headers()
    suffix = uuid.uuid4().hex
    category = post(
        "/categories",
        {
            "name": f"BudgetTypeCat-{suffix}",
            "color": "#336699",
            "category_type": "expense",
        },
        h,
    )
    assert category.status_code == 201, category.text
    category_id = category.json()["id"]

    budget = post(
        "/budgets",
        {
            "category_id": category_id,
            "month": 9,
            "year": 2026,
            "amount": 30000,
        },
        h,
    )
    assert budget.status_code == 201, budget.text
    budget_id = budget.json()["id"]

    rejected = put(f"/budgets/{budget_id}", {"amount": "not-cents"}, h)
    assert rejected.status_code == 400, rejected.text
    assert "error" in rejected.json()

    reloaded = get(f"/budgets/{budget_id}", h)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["amount"] == 30000
