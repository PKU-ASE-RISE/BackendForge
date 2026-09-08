import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-Api-Key": f"probe-org-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_numeric_condition_type_mismatch_defaults():
    h = headers()
    env_id = f"env-{uuid.uuid4().hex}"
    feature_key = f"age-gate-{uuid.uuid4().hex}"

    env_response = requests.post(
        f"{BASE_URL}/api/environments",
        headers=h,
        json={"id": env_id, "name": "Numeric Condition Env"},
        timeout=30,
    )
    assert env_response.status_code == 201

    feature_response = requests.post(
        f"{BASE_URL}/api/features",
        headers=h,
        json={"key": feature_key, "valueType": "string", "defaultValue": "default"},
        timeout=30,
    )
    assert feature_response.status_code == 201

    rule_response = requests.post(
        f"{BASE_URL}/api/features/{feature_key}/rules/{env_id}",
        headers=h,
        json={"type": "force", "value": "adult", "condition": {"age": {"$gt": 18}}},
        timeout=30,
    )
    assert rule_response.status_code == 201

    sdk_response = requests.post(
        f"{BASE_URL}/api/sdk-connections",
        headers=h,
        json={"name": "SDK", "environment": env_id},
        timeout=30,
    )
    assert sdk_response.status_code == 201
    client_key = sdk_response.json()["connection"]["clientKey"]

    eval_response = requests.post(
        f"{BASE_URL}/api/eval/{client_key}",
        json={"attributes": {"id": "user-1", "age": "not-a-number"}},
        timeout=30,
    )

    assert eval_response.status_code == 200
    result = eval_response.json()["features"][feature_key]
    assert result["value"] == "default"
    assert result["source"] == "defaultValue"
