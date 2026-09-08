import os
import time
import uuid

import requests


BASE_URL = (os.environ.get("BASE_URL", "").strip() or "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": "test-api-key-1", "Content-Type": "application/json"}
POLL_TIMEOUT = 5
POLL_INTERVAL = 0.05


def wait_for_activity(transaction_id, subscriber_id):
    """Poll until activity is visible, returning the last HTTP response."""
    deadline = time.monotonic() + POLL_TIMEOUT
    while True:
        response = requests.get(
            f"{BASE_URL}/v1/activity",
            headers=HEADERS,
            params={"transactionId": transaction_id, "subscriberId": subscriber_id},
            timeout=30,
        )
        try:
            ready = bool(response.json().get("data"))
        except (requests.exceptions.JSONDecodeError, AttributeError):
            ready = False
        if response.status_code != 200 or ready or time.monotonic() >= deadline:
            return response
        time.sleep(POLL_INTERVAL)


def test_trigger_to_topic_key_processes_topic():
    marker = uuid.uuid4().hex
    topic_key = f"trigger-topic-{marker}"
    subscriber_id = f"topic-target-{marker}"
    trigger_identifier = f"topic-trigger-{marker}"

    workflow_response = requests.post(
        f"{BASE_URL}/v1/workflows",
        headers=HEADERS,
        json={
            "name": f"Topic trigger {marker}",
            "triggerIdentifier": trigger_identifier,
            "steps": [
                {
                    "channel": "in_app",
                    "template": {"body": "Hello {{name}}"},
                    "order": 1,
                }
            ],
        },
        timeout=30,
    )
    assert workflow_response.status_code == 201

    subscriber_response = requests.post(
        f"{BASE_URL}/v1/subscribers",
        headers=HEADERS,
        json={"subscriberId": subscriber_id},
        timeout=30,
    )
    assert subscriber_response.status_code == 201

    topic_response = requests.post(
        f"{BASE_URL}/v1/topics",
        headers=HEADERS,
        json={"key": topic_key, "name": f"Topic {marker}"},
        timeout=30,
    )
    assert topic_response.status_code == 201

    add_response = requests.post(
        f"{BASE_URL}/v1/topics/{topic_key}/subscribers",
        headers=HEADERS,
        json={"subscriberIds": [subscriber_id]},
        timeout=30,
    )
    assert add_response.status_code == 200

    trigger_response = requests.post(
        f"{BASE_URL}/v1/triggers",
        headers=HEADERS,
        json={
            "workflowIdentifier": trigger_identifier,
            "to": {"topicKey": topic_key},
            "payload": {"name": "Ada"},
        },
        timeout=30,
    )
    assert trigger_response.status_code == 201
    transaction_id = trigger_response.json()["transactionId"]

    activity_response = wait_for_activity(transaction_id, subscriber_id)
    assert activity_response.status_code == 200
    activities = activity_response.json()["data"]
    assert len(activities) == 1
    assert activities[0]["channel"] == "in_app"
    assert activities[0]["status"] in {"pending", "sent", "delivered"}
