import os
import uuid

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


def test_subscription_invalid_started_at_rejected():
    hdr = headers()
    suffix = uuid.uuid4().hex
    customer_id = f"cust-{suffix}"
    plan_code = f"plan-{suffix}"

    assert post("/customers", {"external_id": customer_id, "name": "Invalid Date Customer"}, hdr).status_code == 201
    assert post(
        "/plans",
        {
            "name": "Invalid Date Plan",
            "code": plan_code,
            "interval": "monthly",
            "amount_cents": 500,
            "currency": "USD",
        },
        hdr,
    ).status_code == 201

    sub_resp = post(
        "/subscriptions",
        {
            "external_customer_id": customer_id,
            "plan_code": plan_code,
            "started_at": "not-a-date-time",
        },
        hdr,
    )
    assert sub_resp.status_code == 400

    list_resp = get("/subscriptions", hdr, params={"external_customer_id": customer_id})
    assert list_resp.status_code == 200
    assert list_resp.json()["subscriptions"] == []
