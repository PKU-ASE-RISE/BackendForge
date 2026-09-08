import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"bf-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def post(path, payload, hdr):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=hdr, timeout=30)


def put(path, payload, hdr):
    return requests.put(f"{BASE_URL}{path}", json=payload, headers=hdr, timeout=30)


def get(path, hdr):
    return requests.get(f"{BASE_URL}{path}", headers=hdr, timeout=30)


def test_invoice_update_rejects_foreign_client_id():
    hdr_a = headers()
    hdr_b = headers()

    local_client = post("/api/clients", {"name": f"local-invoice-client-{uuid.uuid4().hex}"}, hdr_a)
    foreign_client = post("/api/clients", {"name": f"foreign-invoice-client-{uuid.uuid4().hex}"}, hdr_b)
    assert local_client.status_code == 201, local_client.text
    assert foreign_client.status_code == 201, foreign_client.text
    local_client_id = local_client.json()["id"]
    foreign_client_id = foreign_client.json()["id"]

    original_items = [{"description": "local work", "quantity": 2, "unit_cost": 1500}]
    invoice = post(
        "/api/invoices",
        {"client_id": local_client_id, "line_items": original_items},
        hdr_a,
    )
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]

    updated = put(
        f"/api/invoices/{invoice_id}",
        {
            "client_id": foreign_client_id,
            "line_items": original_items,
            "discount": 0,
            "discount_type": "amount",
            "tax_rate": 0,
        },
        hdr_a,
    )
    assert updated.status_code == 422, updated.text

    reloaded = get(f"/api/invoices/{invoice_id}", hdr_a)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["client_id"] == local_client_id
