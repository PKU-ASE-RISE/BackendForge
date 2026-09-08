import os
import uuid
from datetime import datetime, timedelta, timezone

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {
        "X-Api-Key": f"org-{uuid.uuid4().hex}",
        "Content-Type": "application/json",
    }


def post(path, payload, hdr):
    return requests.post(f"{BASE_URL}{path}", json=payload, headers=hdr, timeout=30)


def get(path, hdr):
    return requests.get(f"{BASE_URL}{path}", headers=hdr, timeout=30)


def test_invoice_generation_uses_last_invoice_boundary():
    hdr = headers()
    suffix = uuid.uuid4().hex
    customer_id = f"cust-{suffix}"
    plan_code = f"plan-{suffix}"
    metric_code = f"metric-{suffix}"

    assert post("/customers", {"external_id": customer_id, "name": "Boundary Customer"}, hdr).status_code == 201
    assert post(
        "/billable_metrics",
        {"name": "Boundary Count", "code": metric_code, "aggregation_type": "count"},
        hdr,
    ).status_code == 201
    assert post(
        "/plans",
        {
            "name": "Boundary Plan",
            "code": plan_code,
            "interval": "monthly",
            "amount_cents": 1000,
            "currency": "USD",
        },
        hdr,
    ).status_code == 201
    assert post(
        f"/plans/{plan_code}/charges",
        {
            "billable_metric_code": metric_code,
            "charge_model": "standard",
            "properties": {"amount": 300},
        },
        hdr,
    ).status_code == 201

    started_at = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    sub_resp = post(
        "/subscriptions",
        {"external_customer_id": customer_id, "plan_code": plan_code, "started_at": started_at},
        hdr,
    )
    assert sub_resp.status_code == 201
    subscription = sub_resp.json()["subscription"]

    event_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert post(
        "/events",
        {
            "transaction_id": f"tx-{suffix}",
            "external_customer_id": customer_id,
            "code": metric_code,
            "timestamp": event_time,
            "properties": {},
        },
        hdr,
    ).status_code == 200

    first_invoice_resp = post("/invoices/generate", {"subscription_id": subscription["id"]}, hdr)
    assert first_invoice_resp.status_code == 201
    first_invoice_id = first_invoice_resp.json()["invoice"]["id"]
    first_invoice = get(f"/invoices/{first_invoice_id}", hdr).json()["invoice"]
    assert first_invoice["amount_cents"] == 1300

    second_invoice_resp = post("/invoices/generate", {"subscription_id": subscription["id"]}, hdr)
    assert second_invoice_resp.status_code == 201
    second_invoice_id = second_invoice_resp.json()["invoice"]["id"]
    second_invoice = get(f"/invoices/{second_invoice_id}", hdr).json()["invoice"]

    assert second_invoice["amount_cents"] == 1000
    charge_lines = [
        li for li in second_invoice["line_items"]
        if li["item_type"] == "charge" and li["item_code"] == metric_code
    ]
    assert not charge_lines or all(line["quantity"] == 0 and line["amount_cents"] == 0 for line in charge_lines)
