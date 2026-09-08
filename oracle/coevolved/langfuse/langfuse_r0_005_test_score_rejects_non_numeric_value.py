import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def headers():
    return {"X-Api-Key": f"proj-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_score_rejects_non_numeric_value():
    h = headers()
    uid = uuid.uuid4().hex

    trace = requests.post(
        f"{BASE_URL}/api/traces",
        json={"name": f"score-trace-{uid}"},
        headers=h,
        timeout=30,
    )
    assert trace.status_code == 201

    bad_name = f"bad-score-{uid}"
    score = requests.post(
        f"{BASE_URL}/api/scores",
        json={"traceId": trace.json()["id"], "name": bad_name, "value": "not-a-number"},
        headers=h,
        timeout=30,
    )
    assert score.status_code != 201

    listed = requests.get(
        f"{BASE_URL}/api/scores",
        params={"traceId": trace.json()["id"], "name": bad_name},
        headers=h,
        timeout=30,
    )
    assert listed.status_code == 200
    assert listed.json()["data"] == []
