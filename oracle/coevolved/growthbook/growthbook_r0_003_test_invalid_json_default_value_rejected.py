import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def headers():
    return {"X-Api-Key": f"probe-org-{uuid.uuid4().hex}", "Content-Type": "application/json"}


def test_invalid_json_default_value_rejected():
    h = headers()
    feature_key = f"bad-json-{uuid.uuid4().hex}"

    response = requests.post(
        f"{BASE_URL}/api/features",
        headers=h,
        json={"key": feature_key, "valueType": "json", "defaultValue": "{not valid json"},
        timeout=30,
    )

    assert response.status_code == 400

    get_response = requests.get(f"{BASE_URL}/api/features/{feature_key}", headers=h, timeout=30)
    assert get_response.status_code == 404
