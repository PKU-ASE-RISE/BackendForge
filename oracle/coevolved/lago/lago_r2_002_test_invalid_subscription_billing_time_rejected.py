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


def iso_z(value):
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_invalid_subscription_billing_time_rejected():
    hdr = headers()
    suffix = uuid.uuid4().hex
    external_customer_id = f"cust-invalid-billing-time-{suffix}"
    plan_code = f"plan-invalid-billing-time-{suffix}"

    customer_response = post(
        "/customers",
        {"external_id": external_customer_id, "name": "Invalid Billing Time"},
        hdr,
    )
    assert customer_response.status_code == 201

    plan_response = post(
        "/plans",
        {
            "name": "Invalid Billing Time Plan",
            "code": plan_code,
            "interval": "monthly",
            "amount_cents": 1400,
            "currency": "USD",
        },
        hdr,
    )
    assert plan_response.status_code == 201

    started_at = iso_z(datetime.now(timezone.utc) - timedelta(days=1))
    invalid_subscription = post(
        "/subscriptions",
        {
            "external_customer_id": external_customer_id,
            "plan_code": plan_code,
            "billing_time": "quarterly",
            "started_at": started_at,
        },
        hdr,
    )
    assert invalid_subscription.status_code in {400, 422}

    listed = get(
        "/subscriptions",
        hdr,
        params={"external_customer_id": external_customer_id, "per_page": 100},
    )
    assert listed.status_code == 200
    assert listed.json()["subscriptions"] == []
