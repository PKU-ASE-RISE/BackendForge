import os
import uuid

import requests


BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/") or "http://localhost:8000"


def test_channel_kind_requires_destination():
    api_key = f"bf-probe-channel-destination-{uuid.uuid4().hex}"
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

    email_missing_destination = requests.post(
        f"{BASE_URL}/api/v1/channels/",
        json={"kind": "email", "name": f"email-no-destination-{uuid.uuid4().hex}"},
        headers=headers,
        timeout=30,
    )
    webhook_missing_destination = requests.post(
        f"{BASE_URL}/api/v1/channels/",
        json={"kind": "webhook", "name": f"webhook-no-destination-{uuid.uuid4().hex}"},
        headers=headers,
        timeout=30,
    )

    assert email_missing_destination.status_code == 400, email_missing_destination.text
    assert webhook_missing_destination.status_code == 400, webhook_missing_destination.text
