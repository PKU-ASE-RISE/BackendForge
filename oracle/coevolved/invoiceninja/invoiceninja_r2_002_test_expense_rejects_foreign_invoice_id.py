import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"bf-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def post(path, payload, hdr):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=hdr, timeout=30)


def get(path, hdr, params=None):
    return requests.get(f"{BASE_URL}{path}", headers=hdr, params=params, timeout=30)


def test_expense_rejects_foreign_invoice_id():
    hdr_a = headers()
    hdr_b = headers()

    foreign_client = post("/api/clients", {"name": f"foreign-expense-client-{uuid.uuid4().hex}"}, hdr_b)
    assert foreign_client.status_code == 201, foreign_client.text
    foreign_invoice = post(
        "/api/invoices",
        {
            "client_id": foreign_client.json()["id"],
            "line_items": [{"description": "foreign bill", "quantity": 1, "unit_cost": 4400}],
        },
        hdr_b,
    )
    assert foreign_invoice.status_code == 201, foreign_invoice.text
    foreign_invoice_id = foreign_invoice.json()["id"]

    expense = post(
        "/api/expenses",
        {
            "vendor": f"vendor-{uuid.uuid4().hex}",
            "category": "billable",
            "amount": 4400,
            "invoice_id": foreign_invoice_id,
        },
        hdr_a,
    )
    assert expense.status_code == 422, expense.text

    listed = get("/api/expenses", hdr_a)
    assert listed.status_code == 200, listed.text
    assert all(item.get("invoice_id") != foreign_invoice_id for item in listed.json()["data"])
