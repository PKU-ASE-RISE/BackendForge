import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(project_key):
    return {"X-Api-Key": project_key, "Content-Type": "application/json"}


def test_generation_explicit_zero_total_tokens_preserved():
    uid = uuid.uuid4().hex
    h = headers(f"probe-gen-zero-tokens-{uid}")

    trace_resp = requests.post(
        f"{BASE_URL}/api/traces",
        headers=h,
        json={"name": f"trace-{uid}"},
        timeout=30,
    )
    assert trace_resp.status_code == 201
    trace_id = trace_resp.json()["id"]

    gen_resp = requests.post(
        f"{BASE_URL}/api/generations",
        headers=h,
        json={
            "traceId": trace_id,
            "name": f"zero-total-{uid}",
            "usage": {
                "promptTokens": 9,
                "completionTokens": 4,
                "totalTokens": 0,
            },
        },
        timeout=30,
    )
    assert gen_resp.status_code == 201
    gen_id = gen_resp.json()["id"]

    reloaded_gen = requests.get(
        f"{BASE_URL}/api/generations/{gen_id}",
        headers=h,
        timeout=30,
    )
    assert reloaded_gen.status_code == 200
    assert reloaded_gen.json()["usage"]["totalTokens"] == 0

    reloaded_trace = requests.get(
        f"{BASE_URL}/api/traces/{trace_id}",
        headers=h,
        timeout=30,
    )
    assert reloaded_trace.status_code == 200
    assert reloaded_trace.json()["totalTokens"] == 0
