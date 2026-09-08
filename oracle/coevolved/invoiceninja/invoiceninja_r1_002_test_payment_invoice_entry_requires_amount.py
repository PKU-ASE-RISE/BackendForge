import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"payment-entry-amount-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def create_sent_invoice(hdr, amount=100):
    client = requests.post(
        f"{BASE_URL}/api/clients",
        json={"name": f"client-{uuid.uuid4().hex}"},
        headers=hdr,
        timeout=30,
    )
    assert client.status_code == 201
    invoice = requests.post(
        f"{BASE_URL}/api/invoices",
        json={
            "client_id": client.json()["id"],
            "line_items": [{"description": "service", "quantity": 1, "unit_cost": amount}],
        },
        headers=hdr,
        timeout=30,
    )
    assert invoice.status_code == 201
    sent = requests.post(
        f"{BASE_URL}/api/invoices/{invoice.json()['id']}/actions/mark_sent",
        json={},
        headers=hdr,
        timeout=30,
    )
    assert sent.status_code == 200
    return client.json()["id"], invoice.json()["id"]


def test_payment_invoice_entry_requires_amount():
    hdr = headers()
    client_id, invoice_id = create_sent_invoice(hdr, amount=100)

    response = requests.post(
        f"{BASE_URL}/api/payments",
        json={
            "client_id": client_id,
            "amount": 0,
            "date": "2024-04-01",
            "invoices": [{"invoice_id": invoice_id}],
        },
        headers=hdr,
        timeout=30,
    )

    assert response.status_code == 422
    assert "error" in response.json()
