import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_workflow_create_rejects_initial_step_missing_template():
    marker = uuid.uuid4().hex
    trigger_identifier = f"missing-template-{marker}"

    response = requests.post(
        f"{BASE_URL}/v1/workflows",
        headers=HEADERS,
        json={
            "name": f"Missing template {marker}",
            "triggerIdentifier": trigger_identifier,
            "steps": [{"channel": "email", "order": 1}],
        },
        timeout=30,
    )

    assert response.status_code == 422

    list_response = requests.get(
        f"{BASE_URL}/v1/workflows",
        headers=HEADERS,
        params={"page": 0, "limit": 100},
        timeout=30,
    )
    assert list_response.status_code == 200
    assert all(
        workflow["triggerIdentifier"] != trigger_identifier
        for workflow in list_response.json()["data"]
    )
