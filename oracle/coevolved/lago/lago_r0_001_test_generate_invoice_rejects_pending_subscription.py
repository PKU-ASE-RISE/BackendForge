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


def get(path, hdr, params=None):
    return requests.get(f"{BASE_URL}{path}", params=params, headers=hdr, timeout=30)


def test_generate_invoice_rejects_pending_subscription():
    hdr = headers()
    suffix = uuid.uuid4().hex
    customer_id = f"cust-{suffix}"
    plan_code = f"plan-{suffix}"

    assert post("/customers", {"external_id": customer_id, "name": "Pending Invoice Customer"}, hdr).status_code == 201
    assert post(
        "/plans",
        {
            "name": "Pending Invoice Plan",
            "code": plan_code,
            "interval": "monthly",
            "amount_cents": 1200,
            "currency": "USD",
        },
        hdr,
    ).status_code == 201

    future_start = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    sub_resp = post(
        "/subscriptions",
        {
            "external_customer_id": customer_id,
            "plan_code": plan_code,
            "started_at": future_start,
        },
        hdr,
    )
    assert sub_resp.status_code == 201
    subscription = sub_resp.json()["subscription"]
    assert subscription["status"] == "pending"

    invoice_resp = post("/invoices/generate", {"subscription_id": subscription["id"]}, hdr)
    assert invoice_resp.status_code == 400

    invoices_resp = get("/invoices", hdr, params={"external_customer_id": customer_id})
    assert invoices_resp.status_code == 200
    assert all(inv["subscription_id"] != subscription["id"] for inv in invoices_resp.json()["invoices"])
