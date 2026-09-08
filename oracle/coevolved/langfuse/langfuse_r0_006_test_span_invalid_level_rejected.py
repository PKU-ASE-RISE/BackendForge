import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"proj-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_span_invalid_level_rejected():
    h = headers()
    uid = uuid.uuid4().hex

    trace = requests.post(
        f"{BASE_URL}/api/traces",
        json={"name": f"level-trace-{uid}"},
        headers=h,
        timeout=30,
    )
    assert trace.status_code == 201

    bad_name = f"invalid-level-span-{uid}"
    span = requests.post(
        f"{BASE_URL}/api/spans",
        json={"traceId": trace.json()["id"], "name": bad_name, "level": "TRACE"},
        headers=h,
        timeout=30,
    )
    assert span.status_code != 201

    listed = requests.get(
        f"{BASE_URL}/api/spans",
        params={"traceId": trace.json()["id"]},
        headers=h,
        timeout=30,
    )
    assert listed.status_code == 200
    assert bad_name not in {row.get("name") for row in listed.json()["data"]}
