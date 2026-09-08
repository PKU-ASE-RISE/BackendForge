import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"client-expense-cascade-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_delete_client_cascades_expenses():
    hdr = headers()
    client_response = requests.post(
        f"{BASE_URL}/api/clients",
        json={"name": f"client-{uuid.uuid4().hex}"},
        headers=hdr,
        timeout=30,
    )
    assert client_response.status_code == 201
    client_id = client_response.json()["id"]

    invoice_response = requests.post(
        f"{BASE_URL}/api/invoices",
        json={
            "client_id": client_id,
            "line_items": [{"description": "billable setup", "quantity": 1, "unit_cost": 100}],
        },
        headers=hdr,
        timeout=30,
    )
    assert invoice_response.status_code == 201
    invoice_id = invoice_response.json()["id"]

    expense_response = requests.post(
        f"{BASE_URL}/api/expenses",
        json={
            "vendor": f"vendor-{uuid.uuid4().hex}",
            "category": "billable",
            "amount": 25,
            "currency": "USD",
            "invoice_id": invoice_id,
        },
        headers=hdr,
        timeout=30,
    )
    assert expense_response.status_code == 201
    expense_id = expense_response.json()["id"]

    delete_response = requests.delete(
        f"{BASE_URL}/api/clients/{client_id}",
        headers=hdr,
        timeout=30,
    )
    assert delete_response.status_code == 200

    reloaded_expense = requests.get(
        f"{BASE_URL}/api/expenses/{expense_id}",
        headers=hdr,
        timeout=30,
    )
    assert reloaded_expense.status_code == 404
