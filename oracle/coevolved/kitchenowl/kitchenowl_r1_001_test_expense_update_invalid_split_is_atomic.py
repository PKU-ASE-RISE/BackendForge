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


def get(path, headers_, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=headers_, params=params, timeout=30)


def post(path, headers_, payload):
    return requests.post(f"{BASE_URL}{path}", headers=headers_, json=payload, timeout=30)


def put(path, headers_, payload):
    return requests.put(f"{BASE_URL}{path}", headers=headers_, json=payload, timeout=30)


def test_expense_update_invalid_split_is_atomic():
    unique = uuid.uuid4().hex
    household_id = str(uuid.uuid4())
    payer_id = str(uuid.uuid4())
    member_id = str(uuid.uuid4())
    non_member_id = str(uuid.uuid4())
    h_payer = headers(payer_id, household_id)
    h_member = headers(member_id, household_id)

    assert get("/api/households", h_payer).status_code == 200
    assert get("/api/households", h_member).status_code == 200

    original = {
        "amount": 42.5,
        "description": f"original-{unique}",
        "date": "2026-01-05",
        "category": "shared",
        "paidBy": payer_id,
        "splitBetween": [payer_id, member_id],
    }
    created_resp = post("/api/expenses", h_payer, original)
    assert created_resp.status_code == 201
    expense = created_resp.json()

    bad_update = {
        "amount": 999.25,
        "description": f"mutated-{unique}",
        "date": "2026-02-06",
        "category": "should-not-stick",
        "paidBy": payer_id,
        "splitBetween": [payer_id, non_member_id],
    }
    bad_resp = put(f"/api/expenses/{expense['id']}", h_payer, bad_update)
    assert bad_resp.status_code == 400

    # Force an unrelated successful async endpoint to commit on implementations
    # that forgot to rollback after the failed expense update.
    tag_resp = post("/api/tags", h_payer, {"name": f"commit-trigger-{unique}"})
    assert tag_resp.status_code == 201

    list_resp = get("/api/expenses", h_payer)
    assert list_resp.status_code == 200
    reloaded = next(item for item in list_resp.json() if item["id"] == expense["id"])

    assert reloaded["amount"] == original["amount"]
    assert reloaded["description"] == original["description"]
    assert reloaded["date"] == original["date"]
    assert reloaded["category"] == original["category"]
    assert reloaded["paidBy"] == original["paidBy"]
    assert set(reloaded["splitBetween"]) == set(original["splitBetween"])
