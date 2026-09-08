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


def test_invalid_charge_model_rejected():
    hdr = headers()
    suffix = uuid.uuid4().hex
    metric_code = f"metric-invalid-charge-{suffix}"
    plan_code = f"plan-invalid-charge-{suffix}"
    invalid_model = "flat_rate"

    metric_response = post(
        "/billable_metrics",
        {
            "name": "Invalid Charge Metric",
            "code": metric_code,
            "aggregation_type": "count",
        },
        hdr,
    )
    assert metric_response.status_code == 201

    plan_response = post(
        "/plans",
        {
            "name": "Invalid Charge Plan",
            "code": plan_code,
            "interval": "monthly",
            "amount_cents": 1000,
            "currency": "USD",
        },
        hdr,
    )
    assert plan_response.status_code == 201

    invalid_charge = post(
        f"/plans/{plan_code}/charges",
        {
            "billable_metric_code": metric_code,
            "charge_model": invalid_model,
            "properties": {"amount": 25},
        },
        hdr,
    )
    assert invalid_charge.status_code in {400, 422}

    charges_response = get(f"/plans/{plan_code}/charges", hdr)
    assert charges_response.status_code == 200
    assert all(
        charge["charge_model"] != invalid_model
        for charge in charges_response.json()["charges"]
    )
