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


def test_create_experiment_rejects_variation_missing_value():
    headers = make_headers()
    experiment_key = f"bad-var-{uuid.uuid4().hex[:10]}"

    response = api(
        "post",
        "/api/experiments",
        headers,
        json={
            "name": "Bad Variation Experiment",
            "key": experiment_key,
            "variations": [{"name": "Control", "weight": 1.0}],
        },
    )
    assert response.status_code == 400, response.text

    experiments = api("get", "/api/experiments", headers)
    assert experiments.status_code == 200
    assert experiment_key not in {experiment["key"] for experiment in experiments.json()["experiments"]}
