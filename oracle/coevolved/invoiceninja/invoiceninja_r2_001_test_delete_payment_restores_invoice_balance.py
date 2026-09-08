import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"bf-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def post(path, payload, hdr):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=hdr, timeout=30)


def get(path, hdr):
    return requests.get(f"{BASE_URL}{path}", headers=hdr, timeout=30)


def delete(path, hdr):
    return requests.delete(f"{BASE_URL}{path}", headers=hdr, timeout=30)


def test_delete_payment_restores_invoice_balance():
    hdr = headers()
    client = post("/api/clients", {"name": f"delete-payment-{uuid.uuid4().hex}"}, hdr)
    assert client.status_code == 201, client.text
    client_id = client.json()["id"]

    invoice = post(
        "/api/invoices",
        {
            "client_id": client_id,
            "line_items": [{"description": "work", "quantity": 1, "unit_cost": 12000}],
        },
        hdr,
    )
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]
    sent = post(f"/api/invoices/{invoice_id}/actions/mark_sent", {}, hdr)
    assert sent.status_code == 200, sent.text

    payment = post(
        "/api/payments",
        {
            "client_id": client_id,
            "amount": 5000,
            "date": "2025-02-01",
            "invoices": [{"invoice_id": invoice_id, "amount": 5000}],
        },
        hdr,
    )
    assert payment.status_code == 201, payment.text
    payment_id = payment.json()["id"]

    paid_invoice = get(f"/api/invoices/{invoice_id}", hdr)
    assert paid_invoice.status_code == 200, paid_invoice.text
    assert paid_invoice.json()["paid_to_date"] == 5000
    assert paid_invoice.json()["balance"] == 7000

    deleted = delete(f"/api/payments/{payment_id}", hdr)
    assert deleted.status_code == 200, deleted.text

    missing_payment = get(f"/api/payments/{payment_id}", hdr)
    assert missing_payment.status_code == 404, missing_payment.text

    reloaded = get(f"/api/invoices/{invoice_id}", hdr)
    assert reloaded.status_code == 200, reloaded.text
    data = reloaded.json()
    assert data["paid_to_date"] == 0
    assert data["balance"] == data["amount"]
