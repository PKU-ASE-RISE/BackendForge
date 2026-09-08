import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"invoice-discount-type-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def test_invoice_rejects_invalid_discount_type():
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
        f"{BASE_URL}/api/invoices",
        json={
            "client_id": client_id,
            "line_items": [{"description": "work", "quantity": 1, "unit_cost": 100}],
            "discount": 10,
            "discount_type": "not-a-real-discount-type",
        },
        headers=hdr,
        timeout=30,
    )

    assert response.status_code == 422
