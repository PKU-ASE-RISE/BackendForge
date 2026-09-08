import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(project_key):
    return {"X-Api-Key": project_key, "Content-Type": "application/json"}


def test_trace_duration_uses_chronological_iso_offsets():
    uid = uuid.uuid4().hex
    h = headers(f"probe-duration-offset-{uid}")

    trace_resp = requests.post(
        f"{BASE_URL}/api/traces",
        headers=h,
        json={
            "name": f"trace-{uid}",
            "startTime": "2024-01-01T00:00:00Z",
        },
        timeout=30,
    )
    assert trace_resp.status_code == 201
    trace_id = trace_resp.json()["id"]

    span_resp = requests.post(
        f"{BASE_URL}/api/spans",
        headers=h,
        json={
            "traceId": trace_id,
            "name": f"offset-span-{uid}",
            "startTime": "2024-01-01T00:00:00Z",
            "endTime": "2024-01-01T01:00:00+01:00",
        },
        timeout=30,
    )
    assert span_resp.status_code == 201

    gen_resp = requests.post(
        f"{BASE_URL}/api/generations",
        headers=h,
        json={
            "traceId": trace_id,
            "name": f"later-generation-{uid}",
            "startTime": "2024-01-01T00:00:00Z",
            "endTime": "2024-01-01T00:30:00Z",
        },
        timeout=30,
    )
    assert gen_resp.status_code == 201

    detail_resp = requests.get(
        f"{BASE_URL}/api/traces/{trace_id}",
        headers=h,
        timeout=30,
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["duration"] == pytest.approx(30 * 60 * 1000)
