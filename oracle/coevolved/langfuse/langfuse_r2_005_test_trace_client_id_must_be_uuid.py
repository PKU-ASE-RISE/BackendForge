import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers(project_key):
    return {"X-Api-Key": project_key, "Content-Type": "application/json"}


def test_trace_client_id_must_be_uuid():
    uid = uuid.uuid4().hex
    h = headers(f"probe-trace-id-{uid}")
    invalid_id = f"not-a-uuid-{uid}"
    trace_name = f"invalid-id-trace-{uid}"

    create_resp = requests.post(
        f"{BASE_URL}/api/traces",
        headers=h,
        json={"id": invalid_id, "name": trace_name},
        timeout=30,
    )
    assert 400 <= create_resp.status_code < 500

    list_resp = requests.get(
        f"{BASE_URL}/api/traces",
        headers=h,
        params={"limit": 100},
        timeout=30,
    )
    assert list_resp.status_code == 200
    assert invalid_id not in {trace["id"] for trace in list_resp.json()["data"]}
    assert trace_name not in {trace["name"] for trace in list_resp.json()["data"]}
