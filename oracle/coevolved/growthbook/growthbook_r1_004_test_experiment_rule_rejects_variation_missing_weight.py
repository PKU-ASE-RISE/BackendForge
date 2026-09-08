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


def test_experiment_rule_rejects_variation_missing_weight():
    headers = make_headers()
    env_id = f"env-{uuid.uuid4().hex[:10]}"
    feature_key = f"exp-rule-{uuid.uuid4().hex[:10]}"

    assert api("post", "/api/environments", headers, json={"id": env_id, "name": "Experiment Env"}).status_code == 201
    assert api(
        "post",
        "/api/features",
        headers,
        json={"key": feature_key, "valueType": "string", "defaultValue": "control"},
    ).status_code == 201

    bad_rule = api(
        "post",
        f"/api/features/{feature_key}/rules/{env_id}",
        headers,
        json={
            "type": "experiment",
            "value": "control",
            "experimentKey": f"exp-{uuid.uuid4().hex[:10]}",
            "variations": [{"value": "variant"}],
        },
    )
    assert bad_rule.status_code == 400, bad_rule.text

    rules = api("get", f"/api/features/{feature_key}/rules/{env_id}", headers)
    assert rules.status_code == 200
    assert rules.json()["rules"] == []
