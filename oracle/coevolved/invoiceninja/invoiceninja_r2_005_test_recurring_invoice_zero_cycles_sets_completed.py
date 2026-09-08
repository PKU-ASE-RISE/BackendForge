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


def test_recurring_invoice_zero_cycles_sets_completed():
    hdr = headers()
    client = post("/api/clients", {"name": f"recurring-zero-{uuid.uuid4().hex}"}, hdr)
    assert client.status_code == 201, client.text
    client_id = client.json()["id"]

    line_items = [{"description": "subscription", "quantity": 1, "unit_cost": 2500}]
    created = post(
        "/api/recurring_invoices",
        {
            "client_id": client_id,
            "frequency": "monthly",
            "remaining_cycles": 1,
            "line_items": line_items,
        },
        hdr,
    )
    assert created.status_code == 201, created.text
    recurring_id = created.json()["id"]
    assert created.json()["status"] == "active"

    updated = put(
        f"/api/recurring_invoices/{recurring_id}",
        {
            "client_id": client_id,
            "frequency": "monthly",
            "remaining_cycles": 0,
            "line_items": line_items,
        },
        hdr,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["remaining_cycles"] == 0
    assert updated.json()["status"] == "completed"

    reloaded = get(f"/api/recurring_invoices/{recurring_id}", hdr)
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["status"] == "completed"
