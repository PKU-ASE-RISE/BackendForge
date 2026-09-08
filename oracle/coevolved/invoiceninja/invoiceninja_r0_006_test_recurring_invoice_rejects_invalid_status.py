import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"recurring-status-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_recurring_invoice_rejects_invalid_status():
    hdr = headers()
    client_response = requests.post(
        f"{BASE_URL}/api/clients",
        json={"name": f"client-{uuid.uuid4().hex}"},
        headers=hdr,
        timeout=30,
    )
    assert client_response.status_code == 201
    client_id = client_response.json()["id"]

    response = requests.post(
        f"{BASE_URL}/api/recurring_invoices",
        json={
            "client_id": client_id,
            "frequency": "monthly",
            "status": "not-a-valid-status",
            "line_items": [{"description": "retainer", "quantity": 1, "unit_cost": 500}],
        },
        headers=hdr,
        timeout=30,
    )

    assert response.status_code == 422
