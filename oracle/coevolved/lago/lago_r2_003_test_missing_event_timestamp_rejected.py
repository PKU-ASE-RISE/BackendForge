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


def test_missing_event_timestamp_rejected():
    hdr = headers()
    suffix = uuid.uuid4().hex
    external_customer_id = f"cust-missing-event-ts-{suffix}"
    metric_code = f"metric-missing-event-ts-{suffix}"
    transaction_id = f"tx-missing-event-ts-{suffix}"

    customer_response = post(
        "/customers",
        {"external_id": external_customer_id, "name": "Missing Timestamp Customer"},
        hdr,
    )
    assert customer_response.status_code == 201

    metric_response = post(
        "/billable_metrics",
        {
            "name": "Missing Timestamp Metric",
            "code": metric_code,
            "aggregation_type": "count",
        },
        hdr,
    )
    assert metric_response.status_code == 201

    event_response = post(
        "/events",
        {
            "transaction_id": transaction_id,
            "external_customer_id": external_customer_id,
            "code": metric_code,
            "properties": {"units": 1},
        },
        hdr,
    )
    assert event_response.status_code in {400, 422}

    reloaded = get(f"/events/{transaction_id}", hdr)
    assert reloaded.status_code == 404
