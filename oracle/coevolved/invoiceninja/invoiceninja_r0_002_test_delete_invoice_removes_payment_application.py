import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"invoice-payment-delete-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_delete_invoice_removes_payment_application():
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
            "line_items": [{"description": "paid work", "quantity": 1, "unit_cost": 100}],
        },
        headers=hdr,
        timeout=30,
    )
    assert invoice_response.status_code == 201
    invoice_id = invoice_response.json()["id"]

    sent_response = requests.post(
        f"{BASE_URL}/api/invoices/{invoice_id}/actions/mark_sent",
        json={},
        headers=hdr,
        timeout=30,
    )
    assert sent_response.status_code == 200

    payment_response = requests.post(
        f"{BASE_URL}/api/payments",
        json={
            "client_id": client_id,
            "amount": 100,
            "date": "2024-01-02",
            "invoices": [{"invoice_id": invoice_id, "amount": 100}],
        },
        headers=hdr,
        timeout=30,
    )
    assert payment_response.status_code == 201
    payment_id = payment_response.json()["id"]

    delete_response = requests.delete(
        f"{BASE_URL}/api/invoices/{invoice_id}",
        headers=hdr,
        timeout=30,
    )
    assert delete_response.status_code == 200

    reloaded_payment = requests.get(
        f"{BASE_URL}/api/payments/{payment_id}",
        headers=hdr,
        timeout=30,
    )
    assert reloaded_payment.status_code == 200
    applications = reloaded_payment.json()["invoices"]
    assert all(application["invoice_id"] != invoice_id for application in applications)
