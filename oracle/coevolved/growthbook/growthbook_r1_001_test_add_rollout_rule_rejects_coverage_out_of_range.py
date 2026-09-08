import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def make_headers():
    return {"X-Api-Key": f"probe-org-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def api(method, path, headers, json=None, params=None):
    return getattr(requests, method)(
        f"{BASE_URL}{path}",
        headers=headers,
        json=json,
        params=params,
        timeout=30,
    )


def test_add_rollout_rule_rejects_coverage_out_of_range():
    headers = make_headers()
    env_id = f"env-{uuid.uuid4().hex[:10]}"
    feature_key = f"rollout-range-{uuid.uuid4().hex[:10]}"

    assert api("post", "/api/environments", headers, json={"id": env_id, "name": "Rollout Env"}).status_code == 201
    assert api(
        "post",
        "/api/features",
        headers,
        json={"key": feature_key, "valueType": "boolean", "defaultValue": "false"},
    ).status_code == 201

    bad_rule = api(
        "post",
        f"/api/features/{feature_key}/rules/{env_id}",
        headers,
        json={"type": "rollout", "value": "true", "coverage": 1.25},
    )
    assert bad_rule.status_code == 400, bad_rule.text

    rules = api("get", f"/api/features/{feature_key}/rules/{env_id}", headers)
    assert rules.status_code == 200
    assert rules.json()["rules"] == []
