import os
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}


def test_step_update_rejects_invalid_channel():
    marker = uuid.uuid4().hex
    workflow_response = requests.post(
        f"{BASE_URL}/v1/workflows",
        headers=HEADERS,
        json={"name": f"Step update enum {marker}", "triggerIdentifier": f"step-enum-{marker}"},
        timeout=30,
    )
    assert workflow_response.status_code == 201
    workflow_id = workflow_response.json()["id"]

    step_response = requests.post(
        f"{BASE_URL}/v1/workflows/{workflow_id}/steps",
        headers=HEADERS,
        json={"channel": "email", "template": {"subject": "S", "body": "B"}, "order": 1},
        timeout=30,
    )
    assert step_response.status_code == 201
    step_id = step_response.json()["id"]

    patch_response = requests.patch(
        f"{BASE_URL}/v1/workflows/{workflow_id}/steps/{step_id}",
        headers=HEADERS,
        json={"channel": "fax"},
        timeout=30,
    )
    assert patch_response.status_code == 422

    get_response = requests.get(
        f"{BASE_URL}/v1/workflows/{workflow_id}/steps/{step_id}",
        headers=HEADERS,
        timeout=30,
    )
    assert get_response.status_code == 200
    assert get_response.json()["channel"] == "email"
