import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"proj-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_span_parent_must_belong_to_same_trace():
    h = headers()
    uid = uuid.uuid4().hex

    trace_a = requests.post(
        f"{BASE_URL}/api/traces",
        json={"name": f"parent-trace-{uid}"},
        headers=h,
        timeout=30,
    )
    assert trace_a.status_code == 201
    trace_b = requests.post(
        f"{BASE_URL}/api/traces",
        json={"name": f"child-trace-{uid}"},
        headers=h,
        timeout=30,
    )
    assert trace_b.status_code == 201

    parent = requests.post(
        f"{BASE_URL}/api/spans",
        json={"traceId": trace_a.json()["id"], "name": f"root-{uid}"},
        headers=h,
        timeout=30,
    )
    assert parent.status_code == 201

    child_name = f"cross-trace-child-{uid}"
    child = requests.post(
        f"{BASE_URL}/api/spans",
        json={
            "traceId": trace_b.json()["id"],
            "name": child_name,
            "parentSpanId": parent.json()["id"],
        },
        headers=h,
        timeout=30,
    )

    assert child.status_code != 201

    listed = requests.get(
        f"{BASE_URL}/api/spans",
        params={"traceId": trace_b.json()["id"]},
        headers=h,
        timeout=30,
    )
    assert listed.status_code == 200
    assert child_name not in {span.get("name") for span in listed.json()["data"]}
